#!/bin/bash
# Set MilkDropper to a specific mode: desktop, borderless, or window
# NOTE: X11 only — xprop/xdotool have no effect on Wayland sessions.
# Usage: set-mode.sh <mode>

MODE="${1:-desktop}"
STATE_FILE="$HOME/.local/share/milkdropper/.current_mode"

mkdir -p "$(dirname "$STATE_FILE")"
echo "$MODE" > "$STATE_FILE"

# Get projectM window ID
WID=$(xdotool search --classname projectMSDL 2>/dev/null | head -1)
[ -z "$WID" ] && exit 0

# Opacity helper: value is 32-bit uint, 0xFFFFFFFF = fully opaque
set_opacity() {
    local val=$(python3 -c "print(hex(int($1 * 0xFFFFFFFF)))")
    xprop -id "$WID" -f _NET_WM_WINDOW_OPACITY 32c -set _NET_WM_WINDOW_OPACITY "$val"
}

case "$MODE" in
    desktop)
        xprop -id "$WID" -f _NET_WM_WINDOW_TYPE 32a -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_DESKTOP
        xprop -id "$WID" -f _NET_WM_STATE 32a -set _NET_WM_STATE \
            _NET_WM_STATE_BELOW,_NET_WM_STATE_SKIP_TASKBAR,_NET_WM_STATE_SKIP_PAGER,_KDE_NET_WM_STATE_SKIP_SWITCHER,_NET_WM_STATE_STICKY
        set_opacity 0.55
        label="Desktop — 55% opacity"
        ;;
    borderless)
        xprop -id "$WID" -f _NET_WM_WINDOW_TYPE 32a -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_NORMAL
        xprop -id "$WID" -f _NET_WM_STATE 32a -set _NET_WM_STATE ""
        set_opacity 1.0
        label="Borderless Window"
        ;;
    window)
        xprop -id "$WID" -f _NET_WM_WINDOW_TYPE 32a -set _NET_WM_WINDOW_TYPE _NET_WM_WINDOW_TYPE_NORMAL
        xprop -id "$WID" -f _NET_WM_STATE 32a -set _NET_WM_STATE ""
        set_opacity 1.0
        label="Windowed"
        ;;
esac

notify-send -a "MilkDropper" -i "milkdropper-controller" \
    "MilkDropper" "$label" -t 1500
