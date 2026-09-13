#!/bin/bash
#
# Headless Hero macOS .app launcher.
#
# Source of truth for ~/Applications/HeadlessHero.app/Contents/MacOS/HeadlessHero.
# Install it with: scripts/install-mac-launcher.sh
#
# Launches the Electron app only — no browser dev console, no editor. The whole
# dev stack is torn down when the Electron window closes, so this process exits
# and macOS can relaunch the bundle on the next dock click.
#
# Logs: launcher  → ~/Library/Logs/HeadlessHero.log
#       dev stack → /tmp/headless-hero-dev.log
#
# Deliberately not `set -euo pipefail`: `pids=$(lsof -ti … )` below exits 1 on
# the ordinary "port is free" path, and `is_live_child … && pkill` / `kill $pids`
# exit non-zero whenever the target is already gone.
#

LOG_FILE="$HOME/Library/Logs/HeadlessHero.log"

# Appended, not truncated, so a failed launch's log survives the retry. Trimmed
# here rather than rotated — this only ever has one writer.
mkdir -p "$(dirname "$LOG_FILE")" 2>/dev/null
if [ -f "$LOG_FILE" ] && [ "$(stat -f%z "$LOG_FILE" 2>/dev/null || echo 0)" -gt 1048576 ]; then
    tail -n 500 "$LOG_FILE" > "$LOG_FILE.tmp" 2>/dev/null && mv "$LOG_FILE.tmp" "$LOG_FILE"
fi
exec >> "$LOG_FILE" 2>&1

PROJECT_DIR="${HEADLESS_HERO_DIR:-$HOME/git/headless-hero}"
PROJECT_RE=""
BACKEND_PORT=8420
FRONTEND_PORT=5173
# Generous: a first-ever cold start pays for `uv sync` plus Vite's first prebundle.
STARTUP_TIMEOUT=240
# Electron opens a window at t=5s regardless of backend state, so say something
# reassuring long before the hard timeout rather than leaving the user staring
# at a broken window for four minutes. Must stay below STARTUP_TIMEOUT: the
# timeout branch exits first, so an advisory above it would never fire.
STARTUP_ADVISORY=60
OLLAMA_TIMEOUT=15
CLEANED=0
CLEANING=0
DEV_PID=""
OLLAMA_PID=""
WATCHDOG_PID=""
QUIT_REQUESTED=0
MARKER_UNAVAILABLE=0
# Exists once the backend has answered, or once the watchdog has reported a
# terminal problem (the 60s advisory deliberately does not write it, so a later
# crash is still reported). Its absence after the stack exits is what makes a
# silent startup crash audible.
STARTUP_MARKER="${TMPDIR:-/tmp}/headless-hero-startup.$$"

echo ""
echo "=== Headless Hero starting at $(date) ==="

# The marker's absence means "failed", so an unwritable TMPDIR would turn every
# healthy launch into a failure notification. Prove it's writable once, here,
# where there's still a fallback to fall back to — and if even /tmp refuses,
# stay silent rather than crying wolf on every launch. Runs after the banner so
# a complaint lands under this session's header, not the previous one's.
rm -f "$STARTUP_MARKER"
if ! { : > "$STARTUP_MARKER"; } 2>/dev/null; then
    STARTUP_MARKER="/tmp/headless-hero-startup.$$"
    if ! { : > "$STARTUP_MARKER"; } 2>/dev/null; then
        MARKER_UNAVAILABLE=1
        echo "No writable location for the startup marker — startup reporting disabled"
    fi
fi
rm -f "$STARTUP_MARKER"

# Nothing here is attached to a terminal, so failures need to surface somewhere
# the user will actually see. The message is passed as an argv item rather than
# spliced into the AppleScript source, so a quote in a path can't break the very
# notification that exists to report that path.
notify() {
    # Tagged because bash echoes a killed background job's source text into this
    # same log, so bare message text is not greppable evidence of a real report.
    echo "NOTIFICATION: $1"
    osascript - "$1" <<'APPLESCRIPT' 2>/dev/null
on run argv
    display notification (item 1 of argv) with title "Headless Hero"
end run
APPLESCRIPT
}

# .app bundles don't inherit the user's shell environment, so source the profile
# to get Homebrew, uv, npm, node, and other tools on PATH.
if [ -f "$HOME/.zprofile" ]; then
    source "$HOME/.zprofile" 2>/dev/null || true
fi
if [ -f "$HOME/.zshrc" ]; then
    export NONINTERACTIVE=1
    source "$HOME/.zshrc" 2>/dev/null || true
fi

# Prepended, not appended, and verified against `zsh -lic` in this project: the
# terminal resolves node → /opt/homebrew/bin/node and uv → ~/.local/bin/uv, and
# this order reproduces exactly that. Appending instead lets the fnm multishell
# dir that .zshrc prepends win, which silently runs a different Node major
# against the same node_modules — the classic "works in the terminal, not from
# the dock" bug. Re-check both resolutions if you reorder this.
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "PATH: $PATH"
echo "Which node: $(which node 2>/dev/null || echo 'not found') ($(node --version 2>/dev/null || echo 'n/a'))"
echo "Which uv: $(which uv 2>/dev/null || echo 'not found')"
echo "---"

# Kill whatever is LISTENING on a dev port. Restricted to listeners on purpose:
# a bare `lsof -ti tcp:5173` also matches every client connected to Vite's HMR
# socket, so it would SIGKILL the user's browser.
# Usage: free_port <port> [fast]   ("fast" skips the graceful retry loop)
# Returns non-zero if the port is still held after a force kill.
free_port() {
    local port="$1" mode="${2:-}" pids tries i
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
    [ -z "$pids" ] && return 0

    echo "Port $port held by: $pids— terminating"
    kill $pids 2>/dev/null

    tries=5
    [ "$mode" = "fast" ] && tries=1
    for (( i = 0; i < tries; i++ )); do
        sleep 1
        pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
        [ -z "$pids" ] && return 0
    done

    echo "Port $port still held by: $pids— force killing"
    kill -9 $pids 2>/dev/null
    sleep 1
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null | tr '\n' ' ')
    if [ -n "$pids" ]; then
        echo "Port $port STILL held by: $pids"
        return 1
    fi
    return 0
}

# Reap a previous dev stack. Both patterns are project-local absolute paths, so
# they can't match this launcher or an unrelated Electron app. The Electron main
# process holds no listening port, so free_port alone would leave it orphaned.
# Bails on an empty pattern rather than degrading to "every Node project".
reap_stale_stack() {
    [ -n "$PROJECT_RE" ] || return 0
    pkill -f "$PROJECT_RE/node_modules/\.bin/concurrently" 2>/dev/null
    pkill -f "$PROJECT_RE/node_modules/electron/dist/Electron\.app/Contents/MacOS/Electron" 2>/dev/null
}

# Kill only pids that are still children of this shell. A stored pid whose
# process was already reaped is just a number, and this app churns pids hard
# enough (uv, npm, remotion) that reuse within a session isn't exotic.
kill_live_children() {
    local pids
    pids=$(jobs -p 2>/dev/null | tr '\n' ' ')
    [ -n "$pids" ] && kill $pids 2>/dev/null
    return 0
}

is_live_child() {
    [ -n "$1" ] || return 1
    jobs -p 2>/dev/null | grep -qx "$1"
}

# Safety net for the paths concurrently's --kill-others can't cover: this
# launcher being killed (logout, `killall`) or exiting with something still bound.
# It also runs on the early-bail paths, where it doubles as the documented
# startup behavior: a dock launch owns the dev ports, so a stack left running in
# a terminal is fair game.
cleanup() {
    # Idempotency guard rather than `trap - EXIT INT TERM HUP`: resetting a trap
    # from inside its own handler can trip a bash 3.2 bug that logs
    # "run_pending_traps: bad value in trap_list" and resends the signal.
    [ "$CLEANED" -eq 1 ] && return 0
    CLEANING=1
    is_live_child "$OLLAMA_PID" && pkill -P "$OLLAMA_PID" 2>/dev/null
    kill_live_children
    reap_stale_stack
    # "fast": macOS swallows dock clicks while the bundle is still exiting, so a
    # slow teardown reproduces the original symptom in miniature.
    free_port "$BACKEND_PORT" fast
    free_port "$FRONTEND_PORT" fast
    rm -f "$STARTUP_MARKER"
    echo "=== Headless Hero stopped at $(date) ==="
    CLEANED=1
    CLEANING=0
}

# A bare `trap cleanup INT TERM` would run the handler and then *resume* the
# interrupted line with CLEANED already latched, so the resumed code would launch
# a stack that no later cleanup tears down — a signal during the port loops or
# the ollama wait would leave exactly the orphaned listeners this launcher exists
# to prevent.
on_signal() {
    QUIT_REQUESTED=1
    # bash defers a repeat of the *same* signal, but a different one (INT during
    # a TERM teardown) would re-enter here and exit out of the middle of cleanup,
    # skipping the port frees. Let the in-flight cleanup finish instead.
    [ "$CLEANING" -eq 1 ] && return 0
    cleanup
    exit 143
}
trap cleanup EXIT
trap on_signal INT TERM HUP

cd "$PROJECT_DIR" || { notify "Project folder not found - $PROJECT_DIR"; exit 1; }
# Normalize after the cd: the pgrep patterns below are built from this, and a
# trailing slash (`//`) or a symlinked checkout would silently match nothing,
# quietly bringing back the every-other-launch bug.
PROJECT_DIR="$(pwd -P)"
[ -n "$PROJECT_DIR" ] || { notify "Cannot resolve the project folder"; exit 1; }
# pkill -f takes an extended regex, so a `+`, `(` or `[` anywhere in the path
# would otherwise turn reaping into a silent no-op.
PROJECT_RE="$(printf '%s' "$PROJECT_DIR" | sed 's/[][^$.*+?(){}|\\]/\\&/g')"

if ! command -v npm > /dev/null 2>&1; then
    notify "npm not found on PATH - see the log in Console"
    exit 1
fi
if ! grep -q '"dev:app"' package.json; then
    notify "This checkout has no dev:app script - pull the latest main"
    exit 1
fi

reap_stale_stack
free_port "$BACKEND_PORT" || { notify "Port $BACKEND_PORT is stuck - reboot or kill it by hand"; exit 1; }
free_port "$FRONTEND_PORT" || { notify "Port $FRONTEND_PORT is stuck - reboot or kill it by hand"; exit 1; }

# dev:app (not dev) so concurrently's --kill-others tears the backend and Vite
# down as soon as Electron quits.
npm run dev:app > /tmp/headless-hero-dev.log 2>&1 &
DEV_PID=$!
echo "Dev stack running (pid $DEV_PID)."

# Ollama is optional and nothing blocks on it, so it starts after the dev stack
# rather than delaying the window.
if command -v ollama > /dev/null 2>&1 && ! curl -s --connect-timeout 2 --max-time 3 http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    # Wall clock, not iterations: with a bounded curl each pass can cost 4s, so a
    # counted loop would block the launcher (and delay the watchdog) far longer
    # than the cap reads.
    ollama_started=$(date +%s)
    while ! curl -s --connect-timeout 2 --max-time 3 http://localhost:11434/api/tags > /dev/null 2>&1; do
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "ollama serve exited early — continuing without it"
            OLLAMA_PID=""
            break
        fi
        [ "$(( $(date +%s) - ollama_started ))" -ge "$OLLAMA_TIMEOUT" ] && break
        sleep 1
    done
fi

# The ComfyUI and mlx-audio daemons back Local Models Mode. They are optional in
# exactly the same way ollama is: started fire-and-forget after the dev stack,
# never waited on, and never fatal. The app surfaces its own actionable error if
# a modality is set to local while its daemon is down, so a failure here must not
# block the window or the launcher's exit.
LOCAL_ROOT="${HEADLESS_HERO_LOCAL_ROOT:-$HOME/.headless-hero-local}"
COMFY_DIR="$LOCAL_ROOT/ComfyUI"

if [ -d "$COMFY_DIR/.venv" ] && ! curl -s --connect-timeout 2 --max-time 3 http://127.0.0.1:8188/system_stats > /dev/null 2>&1; then
    ( cd "$COMFY_DIR" && ./.venv/bin/python main.py --port 8188 > /tmp/headless-hero-comfyui.log 2>&1 ) &
    echo "Started ComfyUI (local image models)."
fi

if command -v mlx_audio.server > /dev/null 2>&1 && ! curl -s --connect-timeout 2 --max-time 3 http://127.0.0.1:8770/v1/models > /dev/null 2>&1; then
    mlx_audio.server --host 127.0.0.1 --port 8770 > /tmp/headless-hero-mlx-audio.log 2>&1 &
    echo "Started mlx-audio (local voice models)."
fi

# Records that the backend came up. A start that hangs (bound but unresponsive,
# uv blocked on a lock) never dies on its own, so the watchdog reports that case
# itself; a start that crashes is reported by the parent after wait, which can't
# lose the race with its own teardown. curl is bounded so a hung socket can't
# stall the loop past STARTUP_TIMEOUT.
(
    started=$(date +%s)
    advised=0
    while true; do
        if curl -s --connect-timeout 2 --max-time 3 "http://127.0.0.1:$BACKEND_PORT/api/health" > /dev/null 2>&1; then
            { : > "$STARTUP_MARKER"; } 2>/dev/null
            exit 0
        fi
        kill -0 "$DEV_PID" 2>/dev/null || exit 1
        elapsed=$(( $(date +%s) - started ))
        if [ "$elapsed" -ge "$STARTUP_TIMEOUT" ]; then
            { : > "$STARTUP_MARKER"; } 2>/dev/null
            notify "Headless Hero is taking too long to start - check /tmp/headless-hero-dev.log"
            exit 1
        fi
        # Advisory only — no marker, so a later crash is still reported.
        if [ "$advised" -eq 0 ] && [ "$elapsed" -ge "$STARTUP_ADVISORY" ]; then
            advised=1
            notify "Headless Hero is still starting - a first run installs dependencies"
        fi
        sleep 1
    done
) &
WATCHDOG_PID=$!

wait "$DEV_PID" 2>/dev/null

# The stack exited without the backend ever answering, and the user didn't ask
# for that: no window, no error, so say something. The marker is what carries
# this, not QUIT_REQUESTED — the ordinary quit (closing the Electron window)
# sends this script no signal at all, so on that path the marker written at
# health time is the only thing preventing a spurious failure notification.
# (A quit within the first few seconds of a cold start can still trip this — an
# advisory notification beats silence on a real crash.)
if [ "$MARKER_UNAVAILABLE" -eq 0 ] && [ ! -f "$STARTUP_MARKER" ] && [ "$QUIT_REQUESTED" -eq 0 ]; then
    notify "Headless Hero failed to start - check /tmp/headless-hero-dev.log"
fi
