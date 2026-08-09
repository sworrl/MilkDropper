#!/bin/bash
# Cycle MilkDropper window mode: desktop -> borderless -> window -> desktop
# NOTE: X11 only — set-mode.sh drives xprop/xdotool, which do nothing on Wayland.

STATE_DIR="$HOME/.local/share/milkdropper"
STATE_FILE="$STATE_DIR/.current_mode"

# Installed as $prefix/bin/milkdropper-cycle-mode, but set-mode.sh lives in
# $prefix/share/milkdropper — resolve it the same way launch-wallpaper.sh does.
SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SCRIPT")"
if [ ! -f "$DIR/set-mode.sh" ]; then
    for candidate in \
        "$DIR/../share/milkdropper" \
        "/usr/local/share/milkdropper" \
        "/usr/share/milkdropper" \
        "$HOME/.local/share/milkdropper"
    do
        if [ -f "$candidate/set-mode.sh" ]; then
            DIR="$(readlink -f "$candidate")"
            break
        fi
    done
fi

if [ ! -f "$DIR/set-mode.sh" ]; then
    echo "milkdropper: cannot find set-mode.sh" >&2
    exit 1
fi

mkdir -p "$STATE_DIR"
current=$(cat "$STATE_FILE" 2>/dev/null || echo "desktop")

case "$current" in
    desktop)   next="borderless" ;;
    borderless) next="window" ;;
    *)         next="desktop" ;;
esac

exec "$DIR/set-mode.sh" "$next"
