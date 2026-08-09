# MilkDropper RPM — self-contained: bundles an OpenGL ES build of libprojectM 4
# in the private prefix /usr/lib/milkdropper (RPM equivalent of the
# milkdropper-standalone deb). See README for why the GLES build is required.
#
# Rebuild on Fedora:  rpmbuild --rebuild milkdropper-*.src.rpm

%global projectm_version 4.2.0
# The bundled libprojectM lives outside the linker path on purpose; keep RPM
# from exporting or resolving provides/requires against it.
%global __provides_exclude_from ^/usr/lib/milkdropper/lib/.*$
%global __requires_exclude ^libprojectM-4.*$

Name:           milkdropper
Version:        1.1.0
Release:        1%{?dist}
Summary:        KDE Plasma controller for the projectM MilkDrop visualiser
License:        MIT AND LGPL-2.1-or-later
URL:            https://github.com/sworrl/MilkDropper
Source0:        milkdropper-%{version}.tar.gz
Source1:        projectm-%{projectm_version}.tar.gz

BuildRequires:  cmake >= 3.21
BuildRequires:  gcc-c++
BuildRequires:  pkgconfig
BuildRequires:  libglvnd-devel
BuildRequires:  qt6-qtbase-devel >= 6.5
BuildRequires:  qt6-qtdeclarative-devel >= 6.5
BuildRequires:  pulseaudio-libs-devel

Requires:       python3
Requires:       python3-pyqt6
Requires:       plasma-workspace
Requires:       pulseaudio-utils
Recommends:     projectm

Provides:       bundled(libprojectM) = %{projectm_version}

%description
MilkDropper sits in the system tray and manages the projectM music visualiser
in three modes: as a live Plasma wallpaper rendered behind desktop icons, as a
standalone projectMSDL window, or off.

The wallpaper mode is a native Qt Quick renderer that drives libprojectM
directly and captures system audio through PipeWire/PulseAudio. This package
bundles an OpenGL ES build of libprojectM %{projectm_version} under
/usr/lib/milkdropper, because Qt Quick hands out GLES contexts on Wayland and
a desktop-GL libprojectM refuses to initialise on them.

Desktop mode requires Plasma's Qt Quick scene graph to run on OpenGL; see
%{_docdir}/%{name}/README.md for how to enable it.

%prep
%setup -q
mkdir projectm-src
tar xf %{SOURCE1} -C projectm-src --strip-components=1

%build
# 1. Bundled GLES libprojectM, staged locally, final prefix /usr/lib/milkdropper
cmake -S projectm-src -B projectm-build \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX=/usr/lib/milkdropper \
    -DCMAKE_INSTALL_LIBDIR=lib \
    -DENABLE_GLES=ON \
    -DENABLE_PLAYLIST=ON \
    -DENABLE_SYSTEM_PROJECTM_EVAL=OFF \
    -DBUILD_SHARED_LIBS=ON \
    -DENABLE_SDL_UI=OFF \
    -DBUILD_TESTING=OFF
cmake --build projectm-build %{?_smp_mflags}
DESTDIR=$PWD/projectm-stage cmake --install projectm-build

# 2. QML renderer plugin, linked against the stage, RPATH'd to the final prefix
#
# PKG_CONFIG_SYSROOT_DIR rewrites *every* resolved package's paths into the
# stage — including the system 'opengl' package that projectM-4.pc Requires.
# CMake refuses imported targets whose include dirs don't exist, so mirror the
# system include/lib roots inside the stage.
mkdir -p projectm-stage/usr/include \
         projectm-stage%{_libdir} \
         projectm-stage%{_includedir}
export PKG_CONFIG_PATH=$PWD/projectm-stage/usr/lib/milkdropper/lib/pkgconfig
export PKG_CONFIG_SYSROOT_DIR=$PWD/projectm-stage
cmake -S qml-plugin -B qml-plugin/build \
    -DCMAKE_BUILD_TYPE=Release \
    -DPROJECTM_PRIVATE_PREFIX=/usr/lib/milkdropper \
    -DQML_INSTALL_DIR=%{_libdir}/qt6/qml
cmake --build qml-plugin/build %{?_smp_mflags}

%install
# Bundled library (runtime only; headers/pkgconfig/cmake are build-time relics)
DESTDIR=%{buildroot} cmake --install projectm-build
rm -rf %{buildroot}/usr/lib/milkdropper/include \
       %{buildroot}/usr/lib/milkdropper/lib/pkgconfig \
       %{buildroot}/usr/lib/milkdropper/lib/cmake \
       %{buildroot}/usr/lib/milkdropper/lib/libprojectM-4.so \
       %{buildroot}/usr/lib/milkdropper/lib/libprojectM-4-playlist.so

# Everything else through install.sh — the same layout the deb uses
SKIP_BUILD=1 \
PREFIX=/usr \
DESTDIR=%{buildroot} \
QML_INSTALL_DIR=%{_libdir}/qt6/qml \
PROJECTM_PRIVATE_PREFIX=/usr/lib/milkdropper \
    ./install.sh
rm -rf %{buildroot}/usr/share/licenses/milkdropper

%files
%license LICENSE
%doc README.md
%{_bindir}/milkdropper
%{_bindir}/milkdropper-cycle-mode
%{_datadir}/milkdropper/
%{_datadir}/applications/milkdropper.desktop
%{_datadir}/applications/milkdropper-cycle-mode.desktop
%{_datadir}/icons/hicolor/scalable/apps/milkdropper*.svg
%{_datadir}/icons/hicolor/512x512/apps/milkdropper.png
%{_datadir}/plasma/wallpapers/org.projectm.wallpaper/
%{_datadir}/kwin/scripts/projectm-wallpaper/
%{_libdir}/qt6/qml/org/projectm/
/usr/lib/milkdropper/

%changelog
* Sun Aug 09 2026 reaver <agent.jearl@gmail.com> - 1.1.0-1
- Single-instance guard: a second launch opens the running instance's menu
- Multi-monitor fix: preset commands now reach every screen's renderer
- RGB music sync now auto-starts its FFT audio server
- Renderer ported to the projectM 4 C API with a bundled GLES build

* Sat Aug 08 2026 reaver <agent.jearl@gmail.com> - 1.0.0-1
- Initial package
