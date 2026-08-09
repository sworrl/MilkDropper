#!/bin/bash
# Launch the MilkDropper tray controller.
# Right-click tray icon for the mode menu, left-click for a random preset.
#
# Resolves its own install directory so the same script works from the source
# tree, from ~/.local, from /usr/local and from the .deb.

set -euo pipefail

SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SCRIPT")"

# When installed as $prefix/bin/milkdropper, the Python lives in $prefix/share/milkdropper.
if [ ! -f "$DIR/tray-controller.py" ]; then
    for candidate in \
        "$DIR/../share/milkdropper" \
        "/usr/local/share/milkdropper" \
        "/usr/share/milkdropper" \
        "$HOME/.local/share/milkdropper"
    do
        if [ -f "$candidate/tray-controller.py" ]; then
            DIR="$(readlink -f "$candidate")"
            break
        fi
    done
fi

if [ ! -f "$DIR/tray-controller.py" ]; then
    echo "milkdropper: cannot find tray-controller.py" >&2
    exit 1
fi

# No pkill here: the controller is single-instance aware. A second launch
# hands off to the running instance (pops its tray menu) and exits.
exec python3 "$DIR/tray-controller.py" "$@"
