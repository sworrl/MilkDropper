<h1 align="center">
  <br>
  <img src="icons/milkdropper-512.png" width="160" height="160" alt="MilkDropper icon"/>
  <br>
  MilkDropper
  <br>
  <sub><em>a KDE Plasma controller for <a href="https://github.com/projectM-visualizer/projectm">projectM</a> (open-source MilkDrop visualizer)</em></sub>
  <br>
</h1>

<p align="center">
  <a href="https://github.com/projectM-visualizer/projectm"><img src="https://img.shields.io/badge/%F0%9F%8E%B5_ENGINE-projectM-blueviolet?style=for-the-badge&labelColor=1a1a2e" alt="Powered by projectM"></a>
  <a href="https://github.com/sworrl/MilkDropper/releases"><img src="https://img.shields.io/badge/%E2%AC%87%EF%B8%8F_GET-Releases-2ecc71?style=for-the-badge&labelColor=1a1a2e" alt="Download from Releases"></a>
</p>

<p align="center">
  <a href="https://kde.org/plasma-desktop/"><img src="https://img.shields.io/badge/KDE%20Plasma-6-3daee9?style=flat-square&logo=kde&logoColor=white" alt="KDE Plasma 6"></a>
  <a href="https://qt.io"><img src="https://img.shields.io/badge/Qt-6.5%2B-41CD52?style=flat-square&logo=qt&logoColor=white" alt="Qt 6.5+"></a>
  <a href="https://python.org"><img src="https://img.shields.io/badge/Python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white" alt="Python 3.11+"></a>
  <a href="https://pipewire.org"><img src="https://img.shields.io/badge/Audio-PipeWire%20%2F%20PulseAudio-4A90D9?style=flat-square" alt="PipeWire / PulseAudio"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/License-MIT-green?style=flat-square" alt="MIT license"></a>
  <a href="https://github.com/projectM-visualizer/projectm/blob/master/LICENSE.txt"><img src="https://img.shields.io/badge/Engine%20License-LGPL--2.1%2B-orange?style=flat-square" alt="projectM is LGPL-2.1+"></a>
  <a href="https://kernel.org"><img src="https://img.shields.io/badge/Platform-Linux%20only-orange?style=flat-square&logo=linux&logoColor=white" alt="Linux only"></a>
</p>

> MilkDropper is a system tray application and KDE Plasma wallpaper plugin that renders projectM music visualizations on the Linux desktop.

> **Naming & Credit:** **MilkDropper** is this controller application. **[projectM](https://github.com/projectM-visualizer/projectm)** is the underlying C++ visualization engine that handles preset parsing and OpenGL rendering. **MilkDrop** is the original Winamp plugin created by Ryan Geiss. See [Credits & dependencies](#credits--dependencies).

---

## Table of contents

- [What it does](#what-it-does)
- [Screenshots](#screenshots)
- [Credits & dependencies](#credits--dependencies)
- [Requirements](#requirements)
- [OpenGL & GLES caveats](#opengl--gles-caveats)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [How it works](#how-it-works)
- [Building packages](#building-packages)
- [Troubleshooting](#troubleshooting)
- [FAQ](#faq)
- [Platform support](#platform-support)
- [Contributing](#contributing)
- [License & attribution](#license--attribution)

---

## What it does

MilkDropper sits in your system tray and manages three modes of the projectM visualizer:

| Mode | Function |
|---|---|
| **Desktop** | projectM renders as a live Plasma wallpaper behind desktop icons. One renderer runs per screen. |
| **Standard** | projectMSDL runs as a standard window. |
| **Off** | Visualizer process is stopped. |

- **Left-click** tray icon: switch to a random preset.
- **Right-click**: open mode menu, audio routing (PipeWire/PulseAudio), preset navigation, and optional OpenRGB music sync.
- **Single-instance**: launching MilkDropper again opens the menu of the running instance.
- **Multi-monitor**: preset commands apply to renderers on all active screens.
- The wallpaper renderer is a native C++ Qt Quick plugin (`QQuickFramebufferObject`) driving the projectM 4 C API, audio-fed from a lock-free ring buffer and synchronized with the compositor.

---

## Screenshots

<div align="center">

**Desktop mode** (projectM rendering as Plasma wallpaper with tray menu):

![Desktop mode screenshot](docs/screenshot-desktop-mode.png)

![Desktop mode screenshot 2](docs/screenshot-desktop-mode-2.png)

**Tray menus** (audio routing and preset controls):

| Audio routing | Preset controls |
|---|---|
| ![Tray menu with Audio Source submenu](docs/menu-audio-routing.png) | ![Tray menu with Presets submenu](docs/menu-presets.png) |

**Renderer details:**

| Windowed | GLES pipeline |
|---|---|
| ![MilkDrop preset rendered by projectM](docs/screenshot-desktop-gl.png) | ![Renderer on OpenGL ES context](docs/screenshot-gles.png) |

</div>

---

## Credits & dependencies

MilkDropper provides desktop integration and tray controls for external engines and libraries:

### projectM (visualization engine)

**[projectM](https://github.com/projectM-visualizer/projectm)** is an open-source reimplementation of MilkDrop maintained by the projectM team under the LGPL-2.1-or-later license. It parses MilkDrop `.milk` preset files, compiles per-frame and per-vertex equations, evaluates real-time audio FFT data, and renders graphics via OpenGL. Version 4 provides a C API and a separate playlist management library.

| Component | Responsibility |
|---|---|
| projectM | Preset parsing, equation evaluation, audio analysis, OpenGL rendering |
| MilkDropper | Tray menu, PipeWire audio routing, Qt Quick wallpaper surface, Plasma integration |

- Engine: [github.com/projectM-visualizer/projectm](https://github.com/projectM-visualizer/projectm)
- Preset packs: [presets-cream-of-the-crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop) · [presets-milkdrop-texture-pack](https://github.com/projectM-visualizer/presets-milkdrop-texture-pack) · [presets-milkdrop-original](https://github.com/projectM-visualizer/presets-milkdrop-original)
- Frontends: projectMSDL (used in Standard mode), Android, and custom embeddings.

### MilkDrop (original plugin)

**[MilkDrop](http://www.geisswerks.com/milkdrop/)** is a music visualization plugin created by Ryan Geiss for Winamp in 2001. MilkDrop 2 added pixel shaders and established the `.milk` preset format. The source code was released under a BSD-style license.

### Preset authors

Presets are programs written by community artists over two decades, including Flexi, Geiss, Rovastar, Krash, martin, Aderrasi, Eo.S., Zylot, shifter, cope, and stahlregen. Preset filenames contain credit for their respective authors.

### Sister project: PipeDreams

**[PipeDreams](https://github.com/sworrl/pipedreams)** is a PyQt6 audio control center for PipeWire featuring spectrum analysis, a 10-band parametric EQ, and device routing. PipeDreams and MilkDropper operate independently or together: PipeDreams includes a MilkDropper tab to control preset selection and audio devices, while MilkDropper's tray menu includes an option to open PipeDreams. Interoperability details are defined in [`docs/INTEROP.md`](docs/INTEROP.md).

### Project independence

MilkDropper is an independent project. It is not affiliated with or endorsed by the projectM team, Ryan Geiss, or Nullsoft. Report MilkDropper issues directly to this repository.

---

## Requirements

- **KDE Plasma 6** (Wayland or X11)
- **Qt 6.5+** (`qt6-base-dev`, `qt6-declarative-dev`)
- **libprojectM 4** built with `ENABLE_GLES`
- **Python 3.11+** with `PyQt6`
- **PipeWire** or **PulseAudio**
- **projectMSDL** (for Standard mode, available on [Steam](https://store.steampowered.com/app/1358800/projectM_Music_Visualizer/) or from source)

---

## OpenGL & GLES caveats

1. **Desktop mode requires Plasma's Qt Quick scene graph on OpenGL.**
The wallpaper renderer uses `QQuickFramebufferObject`, which requires an OpenGL scene graph. If Plasma uses Vulkan, the wallpaper will render a black screen.

```bash
# Check current backend
kreadconfig6 --file kdeglobals --group QtQuickRendererSettings --key SceneGraphBackend

# Set backend to OpenGL
kwriteconfig6 --file kdeglobals --group QtQuickRendererSettings --key SceneGraphBackend opengl
systemctl --user restart plasma-plasmashell.service
```

This setting applies session-wide. `QSG_RHI_BACKEND` does not override this because KDE's platform theme invokes `QQuickWindow::setGraphicsApi()`.

2. **libprojectM must be compiled with GLES support.**
Qt Quick provides OpenGL ES contexts on Wayland. A desktop OpenGL build of libprojectM will fail during `projectm_create()`. MilkDropper links against a GLES-enabled libprojectM installed at `/usr/lib/milkdropper`.

Standard mode is unaffected by these constraints.

---

## Installation

### Debian / Ubuntu / KDE neon

Install `.deb` packages from [Releases](https://github.com/sworrl/MilkDropper/releases):

```bash
# Standard packages:
sudo dpkg -i libprojectm4-gles_*.deb milkdropper_*.deb

# Standalone package (includes bundled GLES libprojectM):
sudo dpkg -i milkdropper-standalone_*.deb

sudo apt -f install
```

### Fedora / RPM

Rebuild the source RPM to link against distribution dependencies:

```bash
sudo dnf install rpm-build cmake gcc-c++ libglvnd-devel                  qt6-qtbase-devel qt6-qtdeclarative-devel pulseaudio-libs-devel
rpmbuild --rebuild milkdropper-*.src.rpm
sudo dnf install ~/rpmbuild/RPMS/x86_64/milkdropper-*.rpm
```

### From source

```bash
sudo apt install cmake pkg-config qt6-base-dev qt6-declarative-dev                  libpulse-dev python3-pyqt6

git clone https://github.com/sworrl/MilkDropper.git
cd MilkDropper
./install.sh
```

---

## Configuration

Presets, textures, and the `projectMSDL` binary are located in order:

1. `$MILKDROPPER_PRESET_PATH`, `$MILKDROPPER_TEXTURE_PATH`, `$MILKDROPPER_PROJECTMSDL`
2. `~/.config/milkdropper/milkdropper.conf`
3. System default directories and Steam installation paths

```ini
# ~/.config/milkdropper/milkdropper.conf
[Paths]
Presets=/path/to/presets
Textures=/path/to/textures
ProjectMSDL=/path/to/projectMSDL
```

To verify path resolution:

```bash
python3 /usr/share/milkdropper/milkdropper_paths.py
```

Preset collections maintained by the projectM team:
- [Cream of the Crop](https://github.com/projectM-visualizer/presets-cream-of-the-crop) (~10k presets)
- [Original MilkDrop presets](https://github.com/projectM-visualizer/presets-milkdrop-original)
- [Texture pack](https://github.com/projectM-visualizer/presets-milkdrop-texture-pack)

---

## Usage

Launch via application menu (**MilkDropper**) or run `milkdropper`.

**Tray controls:**

| Action | Function |
|---|---|
| Left-click | Select random preset |
| Right-click | Open tray menu |
| Mode → Desktop | Enable wallpaper rendering |
| Mode → Standard | Open projectMSDL window |
| Mode → Off | Stop visualizer |
| Audio Source | Select audio capture device |
| Presets → Next/Prev/Random | Select presets |
| Presets → Lock/Unlock | Lock current preset |
| RGB Music Sync | OpenRGB integration (`openrgb`, `python3-openrgb`) |

**Keyboard shortcuts** (when wallpaper has focus):

| Key | Action |
|---|---|
| `n` / `→` / `↓` | Next preset |
| `p` / `←` / `↑` | Previous preset |
| `r` / space | Random preset |
| `l` | Toggle preset lock |

---

## How it works

```
MilkDropper/
├── controller/
│   ├── tray-controller.py        # PyQt6 system tray (single-instance entry point)
│   ├── milkdropper_paths.py      # Path resolution helper
│   ├── launch-wallpaper.sh       # Executable wrapper script
│   ├── rgb-music.py              # OpenRGB audio sync module
│   ├── audio-fft.py              # PipeWire capture and FFT analysis server
│   ├── cycle-mode.sh             # Mode switching script (X11)
│   ├── set-mode.sh               # X11 xprop setter
│   └── projectm_intercept.c      # LD_PRELOAD shim for SDL event interception
├── plasma-wallpaper/             # Plasma QML wallpaper package
│   └── contents/ui/main.qml      # Main QML wallpaper container
├── kwin-script/                  # KWin desktop positioning script
├── qml-plugin/                   # C++ Qt Quick plugin (org.projectm.renderer)
│   ├── projectmitem.h/cpp        # QQuickFramebufferObject implementation
│   └── CMakeLists.txt            # Qt module build definition
├── packaging/
│   ├── rpm/milkdropper.spec      # RPM spec file
│   └── libprojectm4-gles/        # Debian package files for libprojectM
├── debian/                       # Debian package files
└── icons/scalable/               # SVG icon assets
```

**Desktop mode architecture:**

```
tray menu → wallpaperPlugin = org.projectm.wallpaper
          → plasmashell loads plasma-wallpaper/main.qml
          → instantiates ProjectMItem (org.projectm.renderer module)
          → projectm_create_with_opengl_load_proc(Qt GL resolver)
          → projectm_playlist_add_path(preset directory)
          → AudioCapture thread: pa_simple_read on monitor source
              → lock-free ring buffer → drained in synchronize()
              → projectm_pcm_add_float(..., PROJECTM_STEREO)
          → projectm_opengl_render_frame_fbo(FBO) at compositor vsync
```

---

## Building packages

```bash
# Debian packages
dpkg-buildpackage -us -uc -b

# RPM from source RPM
rpmbuild --rebuild milkdropper-*.src.rpm
```

---

## Troubleshooting

**Wallpaper remains black in Desktop mode:**
- Verify Qt Quick scene graph backend setting: [OpenGL & GLES caveats](#opengl--gles-caveats).
- Check QML module installation: `ls $(qmake6 -query QT_INSTALL_QML)/org/projectm/renderer/`
- Review system logs: `journalctl --user -f | grep ProjectM`

**`projectm_create() failed` error:**
- The installed libprojectM lacks GLES support. Use `-DENABLE_GLES=ON` or install the provided library package.

**Audio capture inactive:**
- Select an active `*.monitor` source in the Audio Source tray menu.
- Verify PipeWire status: `pactl info`

---

## FAQ

**Why does Desktop mode require OpenGL?**
Plasma's wallpaper interface uses Qt Quick framebuffers (`QQuickFramebufferObject`), which require an OpenGL graphics pipeline.

**Can standard `.milk` presets be used?**
Yes. projectM supports MilkDrop `.milk` preset equations and shaders. Point `Presets=` in `milkdropper.conf` to the preset folder.

**Is non-Plasma desktop environments supported?**
Desktop mode requires KDE Plasma 6. Standard mode runs in a standalone window on any desktop environment.

---

## Platform support

> MilkDropper requires KDE Plasma wallpaper APIs, KWin scripting, PipeWire, and DBus. It runs on Linux. Windows and macOS are not supported.

---

## Contributing

Contributions are welcome for packaging, desktop integration, and UI features. Engine improvements should be submitted upstream to [projectM](https://github.com/projectM-visualizer/projectm).

---

## License & attribution

- **MilkDropper**: [MIT](LICENSE)
- **projectM**: [LGPL-2.1-or-later](https://github.com/projectM-visualizer/projectm/blob/master/LICENSE.txt), © projectM team.
- **MilkDrop**: Ryan Geiss / Nullsoft (BSD license).
- **Presets**: Copyrighted by their respective authors.

---

<div align="center">

⭐ [projectM Repository](https://github.com/projectM-visualizer/projectm) · ⬇️ [MilkDropper Releases](https://github.com/sworrl/MilkDropper/releases)

</div>
