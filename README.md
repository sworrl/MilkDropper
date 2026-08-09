<div align="center">

<img src="icons/scalable/milkdropper.svg" width="128" height="128" alt="MilkDropper icon"/>

# MilkDropper

**A KDE Plasma controller for projectM — the open-source MilkDrop visualizer.**  
Live music-reactive visuals as your wallpaper, a floating window, or fullscreen. Controlled from the system tray.

[![KDE Plasma](https://img.shields.io/badge/KDE%20Plasma-6-3daee9?logo=kde&logoColor=white)](https://kde.org/plasma-desktop/)
[![Qt](https://img.shields.io/badge/Qt-6.5%2B-41CD52?logo=qt&logoColor=white)](https://qt.io)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Linux%20only-orange?logo=linux&logoColor=white)](https://kernel.org)

</div>

---

## What it does

MilkDropper sits in your system tray and manages three modes of the [projectM](https://github.com/projectM-visualizer/projectm) visualizer:

| Mode | Description |
|---|---|
| **Desktop** | projectM renders as your live Plasma wallpaper — behind icons, above nothing |
| **Standard** | projectMSDL runs as a regular window you can place anywhere |
| **Off** | Normal desktop, visualizer killed |

Switch modes from the tray menu. Left-click the tray icon for an instant random preset.
The tray menu also exposes per-source **audio routing** (PipeWire/PulseAudio), **preset controls**
(next, previous, random, lock) and an optional **OpenRGB music sync** that drives your RGB
hardware from the same audio.

MilkDropper is **single-instance**: launching it again doesn't spawn a second tray icon — it
just opens the running instance's menu.

The wallpaper renderer is native C++ (a `QQuickFramebufferObject` driving the projectM 4 C API),
one instance per screen, audio-reactive on every monitor.

---

## Screenshots

<div align="center">

| The renderer at work | GLES pipeline |
|---|---|
| ![MilkDrop preset rendering](docs/screenshot-desktop-gl.png) | ![GLES rendering](docs/screenshot-gles.png) |

</div>

---

## Requirements

- **KDE Plasma 6** on Wayland or X11
- **Qt 6.5+** (`qt6-base-dev`, `qt6-declarative-dev` to build)
- **libprojectM 4** built with `ENABLE_GLES` — see below
- **Python 3.11+** with `PyQt6`
- **PipeWire** or **PulseAudio** for audio capture
- **projectMSDL** for Standard mode — Steam (App ID `1358800`) or built from source
- A working brain and a Linux installation

### Two things that will bite you

**1. Desktop mode needs Plasma's Qt Quick scene graph on OpenGL.**
The wallpaper renderer is a `QQuickFramebufferObject`, which is OpenGL-only. If
Plasma runs its scene graph on Vulkan, the wallpaper renders *nothing*, silently.
(MilkDropper warns you with a notification if you enable Desktop mode on the
wrong backend.)

```bash
# check
kreadconfig6 --file kdeglobals --group QtQuickRendererSettings --key SceneGraphBackend
# fix
kwriteconfig6 --file kdeglobals --group QtQuickRendererSettings --key SceneGraphBackend opengl
systemctl --user restart plasma-plasmashell.service
```

This is session-wide — every KDE Qt Quick app switches with it. And note that
`QSG_RHI_BACKEND` does **not** work: KDE's platform theme calls
`QQuickWindow::setGraphicsApi()`, which overrides the environment variable.

**2. libprojectM must be a GLES build.**
Qt Quick hands out OpenGL **ES** contexts on Wayland, and a desktop-GL
libprojectM refuses to initialise on those — `projectm_create()` just returns
NULL. MilkDropper links a libprojectM built with `ENABLE_GLES`, installed in the
private prefix `/usr/lib/milkdropper` so it cannot shadow a system libprojectM
carrying the same SONAME. The packages below handle this for you.

Standard mode is unaffected by both of these and works anywhere.

---

## Installation

### Debian / Ubuntu / KDE neon

Grab the `.deb`s from [Releases](https://github.com/sworrl/MilkDropper/releases):

```bash
# with the library package:
sudo dpkg -i libprojectm4-gles_*.deb milkdropper_*.deb

# or fully self-contained (bundles the GLES libprojectM):
sudo dpkg -i milkdropper-standalone_*.deb

sudo apt -f install   # pull in any missing dependencies
```

### Fedora / RPM

The release ships a source RPM; rebuild it on your machine so it links your
distribution's Qt:

```bash
sudo dnf install rpm-build cmake gcc-c++ libglvnd-devel \
                 qt6-qtbase-devel qt6-qtdeclarative-devel pulseaudio-libs-devel
rpmbuild --rebuild milkdropper-*.src.rpm
sudo dnf install ~/rpmbuild/RPMS/x86_64/milkdropper-*.rpm
```

The binary RPM in the release was built on Ubuntu against Qt 6.11 — it works if
your distro's Qt is ≥ 6.11, otherwise rebuild from the SRPM.

### From source

```bash
sudo apt install cmake pkg-config qt6-base-dev qt6-declarative-dev \
                 libpulse-dev python3-pyqt6

git clone https://github.com/sworrl/MilkDropper.git
cd MilkDropper
./install.sh                     # /usr/local, uses sudo
```

`PREFIX=~/.local ./install.sh` does a user install instead (sudo is still needed
for the one QML module that must live in Qt's import path — plasmashell searches
nowhere else; override with `QML_INSTALL_DIR=`).

`install.sh` expects the GLES libprojectM at `/usr/lib/milkdropper` and prints
the exact build commands if it's missing. The Debian packaging for it lives in
[`packaging/libprojectm4-gles/`](packaging/libprojectm4-gles/).

### Windows

No. Read the [Platform support](#platform-support) section.

---

## Configuration

Presets, textures and the projectMSDL binary are discovered at runtime, in order:

1. `$MILKDROPPER_PRESET_PATH`, `$MILKDROPPER_TEXTURE_PATH`, `$MILKDROPPER_PROJECTMSDL`
2. `~/.config/milkdropper/milkdropper.conf`
3. Well-known locations, including the Steam build of projectM

```ini
# ~/.config/milkdropper/milkdropper.conf
[Paths]
Presets=/path/to/presets
Textures=/path/to/textures
ProjectMSDL=/path/to/projectMSDL
```

Check what was found:

```bash
python3 /usr/share/milkdropper/milkdropper_paths.py     # /usr/local/share for source installs
```

Preset packs, if you don't have the Steam build:

- [projectM texture pack](https://github.com/projectM-visualizer/presets-milkdrop-texture-pack)
- [Cream of the Crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop)
- Any Winamp/MilkDrop `.milk` collection

---

## Usage

Launch from the application launcher (search **MilkDropper**) or run `milkdropper`.
Launching again while it's running just opens the tray menu.

**Tray controls:**

| Action | Result |
|---|---|
| Left-click icon | Random preset |
| Right-click icon | Mode menu |
| Mode → Desktop | projectM as wallpaper |
| Mode → Standard | projectMSDL window |
| Mode → Off | Kill visualizer |
| Audio Source submenu | Route audio per-source |
| Presets → Next/Prev/Random | Navigate presets |
| Presets → Lock/Unlock | Hold current preset |
| RGB Music Sync | Drive OpenRGB devices from the audio (needs `openrgb` + `python3-openrgb`) |

In Desktop mode the wallpaper also takes keys when focused: `n`/`p` next and
previous, `r` or space for random, `l` to toggle the preset lock.

---

## Architecture

```
MilkDropper/
├── controller/
│   ├── tray-controller.py        # PyQt6 system tray — the main entry point (single-instance)
│   ├── milkdropper_paths.py      # Shared preset/texture/binary discovery
│   ├── launch-wallpaper.sh       # Launcher (installed as bin/milkdropper)
│   ├── rgb-music.py              # OpenRGB audio sync (spawns audio-fft.py)
│   ├── audio-fft.py              # PipeWire capture → FFT bands over local HTTP
│   ├── cycle-mode.sh             # Hotkey-friendly mode cycler (X11 only)
│   ├── set-mode.sh               # Raw mode setter (xprop — X11 only)
│   └── projectm_intercept.c      # LD_PRELOAD shim — intercepts SDL quit events
├── plasma-wallpaper/             # Plasma wallpaper package (QML)
│   └── contents/ui/main.qml      # Instantiates the renderer, forwards keys
├── kwin-script/                  # KWin script — pushes projectMSDL behind the desktop
├── qml-plugin/                   # C++ Qt Quick module (org.projectm.renderer)
│   ├── projectmitem.h/cpp        # QQuickFramebufferObject driving the projectM 4 C API
│   └── CMakeLists.txt            # qt_add_qml_module; RPATHs the private GLES libprojectM
├── packaging/
│   ├── rpm/milkdropper.spec      # Self-contained RPM (bundles GLES libprojectM)
│   └── libprojectm4-gles/        # Debian packaging for the library
├── debian/                       # Debian packaging (milkdropper + -standalone)
└── icons/scalable/               # Full SVG icon set (colored + symbolic)
```

**Desktop mode** flow:
`tray → wallpaperPlugin = org.projectm.wallpaper → Plasma loads the QML module →
projectM 4 renders into each screen's FBO → audio captured from PipeWire`

Rendering is driven from `QQuickWindow::afterAnimating` (GUI thread, once per
frame), which self-sustains and throttles to the compositor's pace. Do not move
it back to `afterRendering` — that runs on the render thread, where `update()`
is rejected and the loop stalls after one frame.

The tray talks to the renderers through `/tmp/projectm-cmd`. The file is
mtime-deduplicated per renderer instance and never deleted, so one command
reaches **every** screen.

---

## Building packages

```bash
# Debian packages (milkdropper + milkdropper-standalone)
dpkg-buildpackage -us -uc -b

# RPM
rpmbuild --rebuild milkdropper-*.src.rpm       # from the release SRPM
# or from a checkout: see packaging/rpm/milkdropper.spec header
```

---

## Troubleshooting

**Visualizer doesn't appear in Desktop mode (black wallpaper)**
- Almost always the scene graph backend. See "Two things that will bite you".
- Confirm the QML module is installed: `ls $(qmake6 -query QT_INSTALL_QML)/org/projectm/renderer/`
- Watch it start: `journalctl --user -f | grep ProjectM` while switching modes.
  A healthy start logs the GL context, `projectM 4.x.y instance created`, and a preset count.

**`projectm_create() failed — OpenGL context insufficient?`**
- Your libprojectM is a desktop-GL build but Qt gave it a GLES context. Use the
  packaged library, or rebuild yours with `-DENABLE_GLES=ON`.

**No audio reactivity**
- Tray → Audio Source → pick a `*.monitor` source.
- `pactl info | grep Server` — is PipeWire/PulseAudio up?

**projectMSDL exits immediately (Standard mode)**
- Build the LD_PRELOAD shim: `gcc -shared -fPIC -o projectm_intercept.so controller/projectm_intercept.c -ldl`

---

## Platform support

> **Linux only. That's it. That's the list.**
>
> This project uses KDE Plasma wallpaper APIs, KWin scripting, xprop, xdotool, PipeWire, and DBus — none of which exist on Windows, and none of which we intend to abstract away.
>
> If you're on Windows and want reactive music visualizers: good news, Winamp still exists and MilkDrop 2 runs natively. You're welcome.
>
> If you're on Windows and want to use *this specifically*: **git gud**, install Linux, and come back when you're ready.

macOS *might* work with significant effort. PRs welcome, but don't hold your breath.

---

## Contributing

PRs welcome for: new features, preset integrations, packaging improvements, Wayland fixes.

Please don't open issues asking for Windows support. The answer is no. The answer will always be no.

---

## License

MIT — do whatever you want, just don't remove the attribution.
The packaged libprojectM is LGPL-2.1-or-later, © the projectM team.

---

<div align="center">

*Built for KDE Plasma. Powered by [projectM](https://github.com/projectM-visualizer/projectm). Inspired by the MilkDrop era of desktop personalization.*

</div>
