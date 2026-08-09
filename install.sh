#!/bin/bash
# MilkDropper installer.
#
#   ./install.sh                        # install to /usr/local (uses sudo)
#   PREFIX=~/.local ./install.sh        # user install, no sudo
#   DESTDIR=/tmp/stage ./install.sh     # stage into a directory (used by the .deb build)
#
# The Plasma wallpaper needs its Qt Quick module inside Qt's own QML import
# path, which is NOT under PREFIX. QML_INSTALL_DIR handles that separately.

set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PREFIX="${PREFIX:-/usr/local}"
DESTDIR="${DESTDIR:-}"

# libprojectM built with ENABLE_GLES, kept private so it can't collide with a
# system desktop-GL libprojectM of the same SONAME. See README.
PROJECTM_PRIVATE_PREFIX="${PROJECTM_PRIVATE_PREFIX:-/usr/lib/milkdropper}"

# Ask Qt where QML modules live; plasmashell searches only there.
QML_INSTALL_DIR="${QML_INSTALL_DIR:-$(qmake6 -query QT_INSTALL_QML 2>/dev/null || echo /usr/lib/qt6/qml)}"

SUDO=""
if [ -z "$DESTDIR" ] && [ ! -w "$(dirname "$PREFIX")" ] && [ "$(id -u)" -ne 0 ]; then
    SUDO="sudo"
fi

# The QML module goes to Qt's import path, not $PREFIX — so a user install
# (PREFIX=~/.local, no sudo) still needs sudo for that one step.
SUDO_QML="$SUDO"
if [ -z "$DESTDIR" ] && [ "$(id -u)" -ne 0 ]; then
    qml_probe="$QML_INSTALL_DIR"
    while [ ! -d "$qml_probe" ]; do qml_probe="$(dirname "$qml_probe")"; done
    [ -w "$qml_probe" ] || SUDO_QML="sudo"
fi

say() { printf '\033[1;36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m warning:\033[0m %s\n' "$*" >&2; }

# ---------------------------------------------------------------- prerequisites

# SKIP_BUILD=1: only install. The caller (e.g. the RPM spec) has already
# configured and built qml-plugin/build with its own toolchain/staging env,
# so both the prerequisite checks and the build are theirs to manage.
if [ -n "${SKIP_BUILD:-}" ]; then
    if [ ! -d "$SRC/qml-plugin/build" ]; then
        echo "milkdropper: SKIP_BUILD set but qml-plugin/build does not exist" >&2
        exit 1
    fi
fi

if [ -z "${SKIP_BUILD:-}" ]; then
    missing=()
    for cmd in cmake pkg-config python3 qmake6; do
        command -v "$cmd" >/dev/null || missing+=("$cmd")
    done
    if [ ${#missing[@]} -gt 0 ]; then
        echo "milkdropper: missing build tools: ${missing[*]}" >&2
        echo "  sudo apt install cmake pkg-config python3 qt6-base-dev qt6-declarative-dev libpulse-dev" >&2
        exit 1
    fi

    python3 -c "import PyQt6" 2>/dev/null || warn "PyQt6 not installed — the tray controller will not start (sudo apt install python3-pyqt6)"

    if ! PKG_CONFIG_PATH="$PROJECTM_PRIVATE_PREFIX/lib/pkgconfig" pkg-config --exists projectM-4; then
        echo "milkdropper: no libprojectM 4 found at $PROJECTM_PRIVATE_PREFIX" >&2
        echo "  Build it with GLES support first — Qt Quick hands out GLES contexts:" >&2
        echo "    git clone --recurse-submodules https://github.com/projectM-visualizer/projectm.git" >&2
        echo "    cd projectm && cmake -B build -DENABLE_GLES=ON -DENABLE_PLAYLIST=ON \\" >&2
        echo "        -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=$PROJECTM_PRIVATE_PREFIX" >&2
        echo "    cmake --build build -j\$(nproc) && sudo cmake --install build" >&2
        exit 1
    fi
fi

# ---------------------------------------------------------------- build plugin

if [ -z "${SKIP_BUILD:-}" ]; then
    say "Building the QML renderer plugin"
    cmake -S "$SRC/qml-plugin" -B "$SRC/qml-plugin/build" \
        -DCMAKE_BUILD_TYPE=Release \
        -DPROJECTM_PRIVATE_PREFIX="$PROJECTM_PRIVATE_PREFIX" \
        -DQML_INSTALL_DIR="$QML_INSTALL_DIR" >/dev/null
    cmake --build "$SRC/qml-plugin/build" -j"$(nproc)"
fi

say "Installing QML module into $QML_INSTALL_DIR"
# A previous sudo install leaves a root-owned manifest that a later non-root
# (e.g. DESTDIR-staged) install cannot overwrite. The build dir is ours, so a
# plain unlink always works.
rm -f "$SRC/qml-plugin/build/install_manifest.txt"
$SUDO_QML env DESTDIR="$DESTDIR" cmake --install "$SRC/qml-plugin/build" >/dev/null

# ---------------------------------------------------------------- install files

inst()    { $SUDO install -Dm"$1" "$2" "$DESTDIR$3"; }
instdir() { $SUDO install -d "$DESTDIR$1"; }

say "Installing controller into $PREFIX/share/milkdropper"
instdir "$PREFIX/share/milkdropper"
for f in "$SRC"/controller/*.py "$SRC"/controller/*.sh "$SRC"/controller/projectMSDL.properties; do
    [ -e "$f" ] || continue
    case "$f" in
        *.sh) inst 755 "$f" "$PREFIX/share/milkdropper/$(basename "$f")" ;;
        *)    inst 644 "$f" "$PREFIX/share/milkdropper/$(basename "$f")" ;;
    esac
done
inst 644 "$SRC/controller/projectm_intercept.c" "$PREFIX/share/milkdropper/projectm_intercept.c"

say "Installing launchers into $PREFIX/bin"
inst 755 "$SRC/controller/launch-wallpaper.sh" "$PREFIX/bin/milkdropper"
inst 755 "$SRC/controller/cycle-mode.sh"       "$PREFIX/bin/milkdropper-cycle-mode"

say "Installing icons"
for svg in "$SRC"/icons/scalable/*.svg; do
    inst 644 "$svg" "$PREFIX/share/icons/hicolor/scalable/apps/$(basename "$svg")"
done
[ -f "$SRC/icons/milkdropper-512.png" ] && \
    inst 644 "$SRC/icons/milkdropper-512.png" "$PREFIX/share/icons/hicolor/512x512/apps/milkdropper.png"

say "Installing desktop entries"
for d in "$SRC"/desktop-entries/*.desktop; do
    inst 644 "$d" "$PREFIX/share/applications/$(basename "$d")"
done

say "Installing Plasma wallpaper plugin"
instdir "$PREFIX/share/plasma/wallpapers/org.projectm.wallpaper"
inst 644 "$SRC/plasma-wallpaper/metadata.json" \
         "$PREFIX/share/plasma/wallpapers/org.projectm.wallpaper/metadata.json"
(cd "$SRC/plasma-wallpaper" && find contents -type f) | while read -r rel; do
    inst 644 "$SRC/plasma-wallpaper/$rel" \
             "$PREFIX/share/plasma/wallpapers/org.projectm.wallpaper/$rel"
done

say "Installing KWin script"
instdir "$PREFIX/share/kwin/scripts/projectm-wallpaper"
inst 644 "$SRC/kwin-script/metadata.json" \
         "$PREFIX/share/kwin/scripts/projectm-wallpaper/metadata.json"
(cd "$SRC/kwin-script" && find contents -type f) | while read -r rel; do
    inst 644 "$SRC/kwin-script/$rel" "$PREFIX/share/kwin/scripts/projectm-wallpaper/$rel"
done

inst 644 "$SRC/LICENSE" "$PREFIX/share/licenses/milkdropper/LICENSE"

# ---------------------------------------------------------------- post-install

if [ -z "$DESTDIR" ]; then
    command -v gtk-update-icon-cache >/dev/null && \
        $SUDO gtk-update-icon-cache -q "$PREFIX/share/icons/hicolor/" 2>/dev/null || true
    command -v update-desktop-database >/dev/null && \
        $SUDO update-desktop-database -q "$PREFIX/share/applications" 2>/dev/null || true

    backend="$(kreadconfig6 --file kdeglobals --group QtQuickRendererSettings \
        --key SceneGraphBackend 2>/dev/null || true)"
    if [ "$backend" != "opengl" ]; then
        warn "Plasma's Qt Quick backend is '${backend:-default}', not 'opengl'."
        warn "Desktop (wallpaper) mode renders nothing unless it is OpenGL, because"
        warn "the renderer uses QQuickFramebufferObject. Enable it with:"
        warn "  kwriteconfig6 --file kdeglobals --group QtQuickRendererSettings \\"
        warn "      --key SceneGraphBackend opengl"
        warn "  systemctl --user restart plasma-plasmashell.service"
    fi
fi

say "Done. Launch from your app menu (MilkDropper) or run: milkdropper"
