#!/bin/bash
#
# Headless Hero macOS .app launcher.
#
# This is the source of truth for the launcher used by the dock icon. Install it with:
#   cp scripts/mac-app-launcher.sh ~/Applications/HeadlessHero.app/Contents/MacOS/HeadlessHero
#   chmod +x ~/Applications/HeadlessHero.app/Contents/MacOS/HeadlessHero
#
# It launches only the Electron app (no browser dev console, no editor). The whole
# dev stack is torn down when the Electron window closes, so this process exits and
# macOS can relaunch the bundle on the next dock click.
#
# Log: tail -f ~/Library/Logs/HeadlessHero.log
#

exec > "$HOME/Library/Logs/HeadlessHero.log" 2>&1

PROJECT_DIR="$HOME/git/headless-hero"
BACKEND_PORT=8420
FRONTEND_PORT=5173

echo "Headless Hero starting at $(date)"
echo "---"

# .app bundles don't inherit the user's shell environment, so source the profile
# to get Homebrew, uv, npm, node, and other tools on PATH.
if [ -f "$HOME/.zprofile" ]; then
    source "$HOME/.zprofile"
fi
if [ -f "$HOME/.zshrc" ]; then
    export NONINTERACTIVE=1
    source "$HOME/.zshrc" 2>/dev/null || true
fi

# Ensure common tool paths are available
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"

echo "PATH: $PATH"
echo "Which node: $(which node 2>/dev/null || echo 'not found')"
echo "Which uv: $(which uv 2>/dev/null || echo 'not found')"
echo "---"

# Kill whatever is holding a dev port. A previous run that was force quit (or a
# stack left running in a terminal) orphans uvicorn/vite, and the new backend
# would fail to bind. Returns once the port is free.
free_port() {
    local port="$1" pids
    pids=$(lsof -ti "tcp:$port" 2>/dev/null)
    [ -z "$pids" ] && return 0

    echo "Port $port held by: $pids — terminating"
    kill $pids 2>/dev/null
    for _ in 1 2 3 4 5; do
        sleep 1
        pids=$(lsof -ti "tcp:$port" 2>/dev/null)
        [ -z "$pids" ] && return 0
    done

    echo "Port $port still held by: $pids — force killing"
    kill -9 $pids 2>/dev/null
    sleep 1
}

# Reap a previous dev stack before starting a new one.
pkill -f "$PROJECT_DIR/node_modules/.bin/concurrently" 2>/dev/null
free_port "$BACKEND_PORT"
free_port "$FRONTEND_PORT"

cd "$PROJECT_DIR" || { echo "Project dir $PROJECT_DIR not found"; exit 1; }

# Start ollama only if it's not already listening on :11434
OLLAMA_PID=""
if ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; then
    ollama serve > /tmp/ollama.log 2>&1 &
    OLLAMA_PID=$!
    # Wait for it to come up (max ~15s)
    i=0
    while ! curl -s http://localhost:11434/api/tags > /dev/null 2>&1; do
        (( i++ )); [[ $i -gt 15 ]] && break
        sleep 1
    done
fi

# dev:app (not dev) so concurrently's --kill-others tears the backend and Vite
# down as soon as Electron quits.
npm run dev:app > /tmp/headless-hero-dev.log 2>&1 &
DEV_PID=$!
echo "Headless Hero dev stack running (pid $DEV_PID)."

# Safety net: if this launcher is terminated (logout, `killall`), or the stack
# exits with something still bound, leave no orphans behind.
shutdown() {
    trap - EXIT INT TERM
    kill "$DEV_PID" 2>/dev/null
    pkill -f "$PROJECT_DIR/node_modules/.bin/concurrently" 2>/dev/null
    free_port "$BACKEND_PORT"
    free_port "$FRONTEND_PORT"
    if [[ -n "$OLLAMA_PID" ]]; then
        kill "$OLLAMA_PID" 2>/dev/null
    fi
    echo "Headless Hero stopped at $(date)"
}
trap shutdown EXIT INT TERM

wait "$DEV_PID" 2>/dev/null
