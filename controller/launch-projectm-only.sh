#!/bin/bash
# Launch just projectMSDL (no tray controller).
# The wallpaper plugin renders independently; this is for running the standalone
# visualizer window by hand.

set -euo pipefail

pgrep -x projectMSDL >/dev/null && exit 0

SCRIPT="$(readlink -f "${BASH_SOURCE[0]}")"
DIR="$(dirname "$SCRIPT")"

# Reuse the shared discovery logic rather than guessing a Steam path.
PROJECTM_BIN="$(python3 -c "
import sys; sys.path.insert(0, '$DIR')
import milkdropper_paths
print(milkdropper_paths.find_projectmsdl())
" 2>/dev/null || true)"

if [ -z "$PROJECTM_BIN" ]; then
    echo "milkdropper: projectMSDL not found. Install it, or set Paths/ProjectMSDL" >&2
    echo "             in ~/.config/milkdropper/milkdropper.conf" >&2
    exit 1
fi

PROJECTM_DIR="$(dirname "$PROJECTM_BIN")"

# Ship our tuned properties only if the user has no config of their own.
if [ -f "$DIR/projectMSDL.properties" ] && [ ! -f "$PROJECTM_DIR/projectMSDL.properties" ]; then
    cp "$DIR/projectMSDL.properties" "$PROJECTM_DIR/projectMSDL.properties"
fi

export SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS=0

cd "$PROJECTM_DIR"
exec "$PROJECTM_BIN"
