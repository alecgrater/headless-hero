#!/bin/bash
#
# Install scripts/mac-app-launcher.sh into the Headless Hero .app bundle.
# The bundle executable is a copy, so run this after editing the launcher —
# it syntax-checks the source and verifies the installed copy matches.
#
# Usage: scripts/install-mac-launcher.sh [path/to/Bundle.app/Contents/MacOS/Executable]
#
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/mac-app-launcher.sh"
DEST="${1:-$HOME/Applications/HeadlessHero.app/Contents/MacOS/HeadlessHero}"

[ -f "$SRC" ] || { echo "Missing launcher source: $SRC" >&2; exit 1; }
[ -d "$(dirname "$DEST")" ] || { echo "No app bundle at $(dirname "$DEST")" >&2; exit 1; }

# Gate with /bin/bash explicitly: that is what the bundle's shebang runs (3.2.57),
# and a bash-5-only construct would sail past a Homebrew `bash -n`.
/bin/bash -n "$SRC"
cp "$SRC" "$DEST"
chmod +x "$DEST"

if ! diff -q "$SRC" "$DEST" > /dev/null; then
    echo "Install verification failed: $DEST differs from $SRC" >&2
    exit 1
fi

echo "Installed launcher → $DEST"
