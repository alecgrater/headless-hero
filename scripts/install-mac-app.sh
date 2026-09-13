#!/bin/bash
#
# Create (or refresh) the Headless Hero .app bundle in ~/Applications.
#
# The bundle is a thin wrapper: its executable is a copy of
# scripts/mac-app-launcher.sh, which starts the dev stack and the local model
# daemons. Nothing is compiled and nothing is code-signed — this is a launcher
# for a checkout on this machine, not a distributable app.
#
# Idempotent: re-run it after editing the launcher, the icon, or Info.plist.
# For a launcher-only refresh, scripts/install-mac-launcher.sh is faster.
#
# Usage: scripts/install-mac-app.sh [--dock]
#   --dock   also add the app to the Dock (skipped if already there)
#
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APP="$HOME/Applications/HeadlessHero.app"
CONTENTS="$APP/Contents"
BUNDLE_ID="com.headlesshero.launcher"
ICON_SRC="$REPO/media/icon.png"

ADD_TO_DOCK=0
for arg in "$@"; do
  case "$arg" in
    --dock) ADD_TO_DOCK=1 ;;
    *) echo "Unknown option: $arg"; echo "Usage: $0 [--dock]"; exit 2 ;;
  esac
done

say() { printf '\033[1;36m==>\033[0m %s\n' "$1"; }
ok()  { printf '    \033[0;32mok\033[0m   %s\n' "$1"; }

say "Creating the bundle at $APP"
mkdir -p "$CONTENTS/MacOS" "$CONTENTS/Resources"

# CFBundleIdentifier is what the Dock, Launch Services and the notification
# centre key on, so it must stay stable across reinstalls or macOS treats each
# rebuild as a different app (duplicate Dock tiles, re-asked permissions).
cat > "$CONTENTS/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Headless Hero</string>
    <key>CFBundleDisplayName</key>
    <string>Headless Hero</string>
    <key>CFBundleIdentifier</key>
    <string>$BUNDLE_ID</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleShortVersionString</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>HeadlessHero</string>
    <key>CFBundleIconFile</key>
    <string>icon</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleInfoDictionaryVersion</key>
    <string>6.0</string>
    <key>LSMinimumSystemVersion</key>
    <string>12.0</string>
    <!-- The launcher runs the dev stack and exits when the Electron window
         closes; it is not itself a UI process, so keep it out of the app
         switcher's "not responding" bookkeeping. -->
    <key>NSHighResolutionCapable</key>
    <true/>
</dict>
</plist>
PLIST
ok "wrote Info.plist"

if [ -f "$ICON_SRC" ]; then
    ICONSET="$(mktemp -d)/icon.iconset"
    mkdir -p "$ICONSET"
    # macOS wants the full ladder; a single size renders blurry in the Dock.
    for size in 16 32 64 128 256 512; do
        sips -z "$size" "$size" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}.png" > /dev/null 2>&1
        double=$((size * 2))
        sips -z "$double" "$double" "$ICON_SRC" --out "$ICONSET/icon_${size}x${size}@2x.png" > /dev/null 2>&1
    done
    iconutil -c icns "$ICONSET" -o "$CONTENTS/Resources/icon.icns"
    rm -rf "$(dirname "$ICONSET")"
    ok "built icon.icns from media/icon.png"
else
    echo "    no icon at $ICON_SRC — the bundle will use the generic one"
fi

"$REPO/scripts/install-mac-launcher.sh" "$CONTENTS/MacOS/HeadlessHero"

# Re-register so Launch Services picks up a changed Info.plist or icon instead
# of serving the previous build's metadata from its cache.
LSREGISTER="/System/Library/Frameworks/CoreServices.framework/Frameworks/LaunchServices.framework/Support/lsregister"
[ -x "$LSREGISTER" ] && "$LSREGISTER" -f "$APP" 2>/dev/null || true
touch "$APP"
ok "registered with Launch Services"

if [ "$ADD_TO_DOCK" = "1" ]; then
    say "Adding to the Dock"
    if defaults read com.apple.dock persistent-apps 2>/dev/null | grep -q "HeadlessHero.app"; then
        ok "already in the Dock"
    else
        # -array-add appends to the existing array; it does not replace it.
        defaults write com.apple.dock persistent-apps -array-add "<dict><key>tile-data</key><dict><key>file-data</key><dict><key>_CFURLString</key><string>$APP</string><key>_CFURLStringType</key><integer>0</integer></dict></dict></dict>"
        killall Dock
        ok "added to the Dock"
    fi
fi

say "Headless Hero is installed at $APP"
echo "    Launcher log: ~/Library/Logs/HeadlessHero.log"
echo "    Dev stack log: /tmp/headless-hero-dev.log"
