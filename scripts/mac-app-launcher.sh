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
# Deliberately not `set -euo pipefail`: the `[ -z "$pids" ] && return 0` guards
# and `(( i++ ))` below both return non-zero during normal operation.
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
BACKEND_PORT=8420
FRONTEND_PORT=5173
STARTUP_TIMEOUT=120
DEV_PID=""
OLLAMA_PID=""
WATCHDOG_PID=""

echo ""
echo "=== Headless Hero starting at $(date) ==="

# Nothing here is attached to a terminal, so failures need to surface somewhere
# the user will actually see. The message is passed as an argv item rather than
# spliced into the AppleScript source, so a quote in a path can't break the very
# notification that exists to report that path.
notify() {
    echo "$1"
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
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null)
    [ -z "$pids" ] && return 0

    echo "Port $port held by: $(echo $pids) — terminating"
    kill $pids 2>/dev/null

    tries=5
    [ "$mode" = "fast" ] && tries=1
    for (( i = 0; i < tries; i++ )); do
        sleep 1
        pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null)
        [ -z "$pids" ] && return 0
    done

    echo "Port $port still held by: $pids — force killing"
    kill -9 $pids 2>/dev/null
    sleep 1
    pids=$(lsof -ti "tcp:$port" -sTCP:LISTEN 2>/dev/null)
    if [ -n "$pids" ]; then
        echo "Port $port STILL held by: $pids"
        return 1
    fi
    return 0
}

# Reap a previous dev stack. Both patterns are project-local absolute paths, so
# they can't match this launcher or an unrelated Electron app. The Electron main
# process holds no listening port, so free_port alone would leave it orphaned.
reap_stale_stack() {
    pkill -f "$PROJECT_DIR/node_modules/.bin/concurrently" 2>/dev/null
    pkill -f "$PROJECT_DIR/node_modules/electron/dist/Electron.app/Contents/MacOS/Electron" 2>/dev/null
}

# Safety net for the paths concurrently's --kill-others can't cover: this
# launcher being killed (logout, `killall`) or exiting with something still bound.
# It also runs on the early-bail paths, where it doubles as the documented
# startup behavior: a dock launch owns the dev ports, so a stack left running in
# a terminal is fair game.
cleanup() {
    trap - EXIT INT TERM HUP
    # First, so the watchdog can't see DEV_PID die and cry failure on a quit the
    # user asked for.
    [ -n "$WATCHDOG_PID" ] && kill "$WATCHDOG_PID" 2>/dev/null
    [ -n "$DEV_PID" ] && kill "$DEV_PID" 2>/dev/null
    reap_stale_stack
    # "fast": macOS swallows dock clicks while the bundle is still exiting, so a
    # slow teardown reproduces the original symptom in miniature.
    free_port "$BACKEND_PORT" fast
    free_port "$FRONTEND_PORT" fast
    if [ -n "$OLLAMA_PID" ]; then
        pkill -P "$OLLAMA_PID" 2>/dev/null
        kill "$OLLAMA_PID" 2>/dev/null
    fi
    echo "=== Headless Hero stopped at $(date) ==="
}
trap cleanup EXIT INT TERM HUP

cd "$PROJECT_DIR" || { notify "Project folder not found - $PROJECT_DIR"; exit 1; }
# Normalize after the cd: reap_stale_stack interpolates PROJECT_DIR into pgrep
# patterns, and a trailing slash (`//`) or a symlinked checkout would silently
# match nothing, quietly bringing back the every-other-launch bug.
PROJECT_DIR="$(pwd -P)"

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
if command -v ollama > /dev/null 2>&1 && ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    i=0
    while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
        if ! kill -0 "$OLLAMA_PID" 2>/dev/null; then
            echo "ollama serve exited early — continuing without it"
            OLLAMA_PID=""
            break
        fi
        (( i++ )); [[ $i -gt 15 ]] && break
        sleep 1
    done
fi

# A stack that dies — or hangs — before the backend ever answers means no window
# and no error, which is indistinguishable from the bug this launcher fixes.
# Exits silently the moment the backend is healthy; cleanup() kills it on quit.
(
    waited=0
    while true; do
        curl -s "http://127.0.0.1:$BACKEND_PORT/api/health" > /dev/null 2>&1 && exit 0
        kill -0 "$DEV_PID" 2>/dev/null || break
        waited=$(( waited + 1 ))
        if [ "$waited" -ge "$STARTUP_TIMEOUT" ]; then
            notify "Headless Hero is taking too long to start - check /tmp/headless-hero-dev.log"
            exit 1
        fi
        sleep 1
    done
    notify "Headless Hero failed to start - check /tmp/headless-hero-dev.log"
) &
WATCHDOG_PID=$!

wait "$DEV_PID" 2>/dev/null
