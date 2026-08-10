#!/usr/bin/env python3
"""MilkDropper tray controller.

Modes:
  - Desktop:  projectM renders directly as Plasma wallpaper (behind icons)
  - Standard: Standalone projectMSDL window
  - Off:      Normal desktop
"""

import shutil
import subprocess
import sys
import os
import signal
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import milkdropper_paths as paths

from PyQt6.QtWidgets import QApplication, QSystemTrayIcon, QMenu
from PyQt6.QtGui import QIcon, QAction, QActionGroup, QCursor
from PyQt6.QtCore import QTimer, pyqtSignal
from PyQt6.QtNetwork import QLocalServer, QLocalSocket

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
RGB_SCRIPT = os.path.join(SCRIPT_DIR, "rgb-music.py")
ORIGINAL_WALLPAPER = "org.kde.image"
PROJECTM_WALLPAPER = "org.projectm.wallpaper"

__version__ = "1.2.0"

# Local-socket name for the single-instance handshake. Per-user because the
# socket lives in the user's runtime dir.
INSTANCE_KEY = "milkdropper-tray"


def poke_running_instance():
    """If another MilkDropper is already running, ask it to show its menu.

    Returns True when a running instance answered (i.e. this process should
    exit instead of starting a duplicate tray icon).
    """
    sock = QLocalSocket()
    sock.connectToServer(INSTANCE_KEY)
    if not sock.waitForConnected(500):
        return False
    sock.write(b"show-menu")
    sock.flush()
    sock.waitForBytesWritten(500)
    sock.disconnectFromServer()
    return True

# Qt ships the tool as qdbus6 on some distros and plain qdbus on others.
QDBUS = shutil.which("qdbus6") or shutil.which("qdbus") or "qdbus"


def run(cmd, **kw):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True, **kw)


def get_connected_screens():
    """Return list of dicts describing active screens."""
    screens = []
    qt_screens = QGuiApplication.screens()
    for idx, scr in enumerate(qt_screens):
        name = scr.name()
        label = f"Screen {idx} ({name})"
        screens.append({"index": idx, "name": name, "label": label})
    if not screens:
        screens = [{"index": 0, "name": "Default", "label": "Screen 0"}]
    return screens


def plasma_get_desktop_wallpapers():
    """Return dict of screen_index -> wallpaperPlugin."""
    result = run(f"""{QDBUS} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "
        var d = desktops(); var res = [];
        for (var i = 0; i < d.length; i++) res.push(d[i].screen + ':' + d[i].wallpaperPlugin);
        print(res.join(';'));
    " """)
    mapping = {}
    if result.stdout.strip():
        for item in result.stdout.strip().split(";"):
            if ":" in item:
                parts = item.split(":", 1)
                try:
                    mapping[int(parts[0])] = parts[1].strip()
                except ValueError:
                    pass
    return mapping


def plasma_set_screen_wallpaper(screen_index, plugin):
    """Set wallpaper plugin for a specific screen index."""
    run(f"""{QDBUS} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "
        var d = desktops();
        for (var i = 0; i < d.length; i++) {{
            if (d[i].screen == {screen_index}) d[i].wallpaperPlugin = '{plugin}';
        }}
    " """)


def get_screen_audio_source(screen_index):
    try:
        with open(f"/tmp/projectm-audio-source-{screen_index}") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def set_screen_audio_source(screen_index, name):
    filepath = f"/tmp/projectm-audio-source-{screen_index}"
    if name:
        with open(filepath, "w") as f:
            f.write(name)
    else:
        if os.path.exists(filepath):
            os.remove(filepath)
    send_wallpaper_cmd(f"{screen_index}:reload-audio")


def plasma_get_wallpaper():
    result = run(f"""{QDBUS} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "
        var d = desktops(); print(d[0].wallpaperPlugin);
    " """)
    return result.stdout.strip()


def plasma_set_wallpaper(plugin):
    run(f"""{QDBUS} org.kde.plasmashell /PlasmaShell org.kde.PlasmaShell.evaluateScript "
        var d = desktops();
        for (var i = 0; i < d.length; i++) d[i].wallpaperPlugin = '{plugin}';
    " """)


def scenegraph_backend():
    """Plasma's Qt Quick backend. Desktop mode needs 'opengl'."""
    r = run("kreadconfig6 --file kdeglobals --group QtQuickRendererSettings "
            "--key SceneGraphBackend")
    return r.stdout.strip()


def warn_if_not_opengl():
    """Desktop mode renders nothing on a non-OpenGL scene graph, and does so
    silently — so say something rather than leaving a black wallpaper."""
    backend = scenegraph_backend()
    if backend == "opengl":
        return
    subprocess.Popen(
        ["notify-send", "-a", "MilkDropper", "-i", "milkdropper",
         "-u", "critical", "MilkDropper",
         f"Desktop mode needs Plasma's Qt Quick backend on OpenGL "
         f"(currently '{backend or 'default'}').\n\n"
         f"kwriteconfig6 --file kdeglobals --group QtQuickRendererSettings "
         f"--key SceneGraphBackend opengl\n"
         f"systemctl --user restart plasma-plasmashell.service"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def kill_projectm():
    run("killall projectMSDL 2>/dev/null")


def send_wallpaper_cmd(cmd):
    """Send a command to the running wallpaper plugin via the command file."""
    with open("/tmp/projectm-cmd", "w") as f:
        f.write(cmd)


def list_audio_sources():
    """Return list of (name, description) for available PipeWire sources."""
    result = run("pactl list short sources")
    names = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            names.append(parts[1])

    descriptions = {}
    current = None
    for line in run("pactl list sources").stdout.splitlines():
        line = line.strip()
        if line.startswith("Name:"):
            current = line.split(":", 1)[1].strip()
        elif line.startswith("Description:") and current:
            descriptions[current] = line.split(":", 1)[1].strip()
            current = None
    return [(n, descriptions.get(n, n)) for n in names]


def get_current_source():
    try:
        with open("/tmp/projectm-audio-source") as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def set_audio_source(name):
    """Persist source choice and tell plugin to reconnect (only if source changed)."""
    old = get_current_source()
    with open("/tmp/projectm-audio-source", "w") as f:
        f.write(name)
    if name != old:
        send_wallpaper_cmd("reload-audio")


def auto_detect_audio_source(on_found):
    """Background thread: find the active audio monitor and call on_found(name).

    Checks for any sink in RUNNING state and uses its monitor.
    Does nothing if user already has a source configured.
    """
    def _detect():
        if get_current_source():
            return

        monitors = [n for n, _ in list_audio_sources() if n.endswith(".monitor")]
        if not monitors:
            return

        for line in run("pactl list sinks short").stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 2 and parts[-1].strip() == "RUNNING":
                mon = parts[1].strip() + ".monitor"
                if mon in monitors:
                    on_found(mon)
                    return

    threading.Thread(target=_detect, daemon=True).start()


def start_projectm_standard():
    """Launch projectMSDL. Returns False (and notifies) if it isn't installed."""
    binary = paths.find_projectmsdl()
    if not binary:
        subprocess.Popen(
            ["notify-send", "-a", "MilkDropper", "-i", "milkdropper",
             "MilkDropper", "projectMSDL not found \u2014 install it, or set "
             "Paths/ProjectMSDL in ~/.config/milkdropper/milkdropper.conf"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        return False

    kill_projectm()
    env = os.environ.copy()
    env["SDL_VIDEO_MINIMIZE_ON_FOCUS_LOSS"] = "0"
    subprocess.Popen(
        [binary], cwd=os.path.dirname(binary), env=env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return True


def load_icon(name):
    """Load icon by name — theme lookup first, then any XDG data dir (SVG or PNG)."""
    icon = QIcon.fromTheme(name)
    if not icon.isNull():
        return icon
    for base in paths.data_dirs():
        for path in (f"{base}/icons/hicolor/scalable/apps/{name}.svg",
                     f"{base}/icons/hicolor/512x512/apps/{name}.png",
                     f"{base}/icons/hicolor/256x256/apps/{name}.png"):
            if os.path.exists(path):
                return QIcon(path)
    return QIcon()


MODES = {
    "off":      {"label": "Off",      "icon": "milkdropper-off"},
    "desktop":  {"label": "Desktop",  "icon": "milkdropper-desktop"},
    "standard": {"label": "Standard", "icon": "milkdropper-standard"},
}


class TrayController(QSystemTrayIcon):
    _audio_detected = pyqtSignal(str)

    def __init__(self):
        super().__init__()
        self._rgb_proc = None

        QLocalServer.removeServer(INSTANCE_KEY)
        self._instance_server = QLocalServer(self)
        self._instance_server.newConnection.connect(self._on_second_instance)
        if not self._instance_server.listen(INSTANCE_KEY):
            print(f"warning: single-instance socket unavailable: "
                  f"{self._instance_server.errorString()}", file=sys.stderr)

        current_wp = plasma_get_wallpaper()
        if current_wp == PROJECTM_WALLPAPER:
            self.current_mode = "desktop"
        else:
            self.current_mode = "off"

        menu = QMenu()
        self.mode_group = QActionGroup(menu)
        self.mode_group.setExclusive(True)
        self.mode_actions = {}

        for mode_id, info in MODES.items():
            action = QAction(load_icon(info["icon"]), info["label"], menu)
            action.setCheckable(True)
            action.triggered.connect(lambda checked, m=mode_id: self.set_mode(m))
            self.mode_group.addAction(action)
            self.mode_actions[mode_id] = action
            menu.addAction(action)

        self.mode_actions[self.current_mode].setChecked(True)

        # Per-screen Desktop Mode toggle sub-menu
        self.screen_mode_menu = menu.addMenu("Per-Screen Mode")
        self.screen_mode_menu.aboutToShow.connect(self._populate_screen_mode_menu)

        menu.addSeparator()

        # Audio Source submenu (dynamic — refreshes on open)
        self.audio_menu = menu.addMenu("Audio Source")
        self.audio_menu.aboutToShow.connect(self._populate_audio_menu)

        # Preset controls (Global + Per-Screen)
        self.preset_menu = menu.addMenu("Presets")
        self.preset_menu.aboutToShow.connect(self._populate_preset_menu)

        menu.addSeparator()

        # Sister project: PipeDreams (audio control center). Shown only when
        # installed — the repos are independent and neither requires the other.
        pipedreams_bin = paths.find_pipedreams()
        if pipedreams_bin:
            pd_action = QAction("Open PipeDreams", menu)
            pd_action.setToolTip("PipeDreams — audio control center (sister project)")
            pd_action.triggered.connect(
                lambda checked, b=pipedreams_bin: subprocess.Popen(
                    [b], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))
            menu.addAction(pd_action)
            menu.addSeparator()

        self.rgb_action = QAction("RGB Music Sync", menu)
        self.rgb_action.setCheckable(True)
        self.rgb_action.triggered.connect(self._toggle_rgb_sync)
        menu.addAction(self.rgb_action)

        menu.addSeparator()

        quit_action = QAction("Quit Controller", menu)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(quit_action)

        self.setContextMenu(menu)
        self.activated.connect(self.on_click)
        self._audio_detected.connect(self._on_audio_detected)
        self._update_icon()
        self.show()

        auto_detect_audio_source(self._audio_detected.emit)

    def _on_second_instance(self):
        # Message-based, not connection-based: sister apps (PipeDreams) probe
        # this socket with "ping" to see if we're running — that must NOT pop
        # the menu in the user's face. Only an explicit "show-menu" does.
        while self._instance_server.hasPendingConnections():
            conn = self._instance_server.nextPendingConnection()
            conn.readyRead.connect(lambda c=conn: self._handle_instance_message(c))
            conn.disconnected.connect(conn.deleteLater)

    def _handle_instance_message(self, conn):
        msg = bytes(conn.readAll()).strip()
        if msg == b"show-menu":
            # Second launch by the user — show the running instance's menu.
            # It pops at the cursor; on Wayland the compositor decides final
            # placement, but it is always shown.
            menu = self.contextMenu()
            if menu:
                menu.popup(QCursor.pos())
        elif msg == b"ping":
            conn.write(f"milkdropper {__version__} mode={self.current_mode}\n".encode())
            conn.flush()
        conn.disconnectFromServer()

    def _on_audio_detected(self, source_name):
        if get_current_source():
            return
        set_audio_source(source_name)

    def _populate_screen_mode_menu(self):
        self.screen_mode_menu.clear()
        screens = get_connected_screens()
        wallpapers = plasma_get_desktop_wallpapers()

        for s in screens:
            s_idx = s["index"]
            label = s["label"]
            current_wp = wallpapers.get(s_idx, plasma_get_wallpaper())
            is_desktop = (current_wp == PROJECTM_WALLPAPER)

            sm = self.screen_mode_menu.addMenu(label)

            on_act = QAction("Desktop Mode", sm)
            on_act.setCheckable(True)
            on_act.setChecked(is_desktop)
            on_act.triggered.connect(lambda checked, idx=s_idx: self._set_single_screen_mode(idx, True))
            sm.addAction(on_act)

            off_act = QAction("Off (Normal Wallpaper)", sm)
            off_act.setCheckable(True)
            off_act.setChecked(not is_desktop)
            off_act.triggered.connect(lambda checked, idx=s_idx: self._set_single_screen_mode(idx, False))
            sm.addAction(off_act)

    def _set_single_screen_mode(self, screen_index, enable):
        plugin = PROJECTM_WALLPAPER if enable else ORIGINAL_WALLPAPER
        warn_if_not_opengl()
        plasma_set_screen_wallpaper(screen_index, plugin)
        if enable:
            send_wallpaper_cmd(f"{screen_index}:reload-audio")

    def _populate_preset_menu(self):
        self.preset_menu.clear()
        screens = get_connected_screens()

        # Global (All Screens)
        for label, cmd in [("Random", "all:random"), ("Next", "all:next"), ("Previous", "all:prev")]:
            a = QAction(f"{label} (All Screens)", self.preset_menu)
            a.triggered.connect(lambda checked, c=cmd: send_wallpaper_cmd(c))
            self.preset_menu.addAction(a)

        lock_a = QAction("Lock (All Screens)", self.preset_menu)
        lock_a.triggered.connect(lambda: send_wallpaper_cmd("all:lock"))
        self.preset_menu.addAction(lock_a)

        unlock_a = QAction("Unlock (All Screens)", self.preset_menu)
        unlock_a.triggered.connect(lambda: send_wallpaper_cmd("all:unlock"))
        self.preset_menu.addAction(unlock_a)

        if len(screens) > 1:
            self.preset_menu.addSeparator()
            for s in screens:
                s_idx = s["index"]
                label = s["label"]
                sm = self.preset_menu.addMenu(label)

                for p_label, cmd in [("Random", f"{s_idx}:random"), ("Next", f"{s_idx}:next"), ("Previous", f"{s_idx}:prev")]:
                    a = QAction(p_label, sm)
                    a.triggered.connect(lambda checked, c=cmd: send_wallpaper_cmd(c))
                    sm.addAction(a)
                sm.addSeparator()
                la = QAction("Lock current", sm)
                la.triggered.connect(lambda checked, idx=s_idx: send_wallpaper_cmd(f"{idx}:lock"))
                sm.addAction(la)
                ula = QAction("Unlock", sm)
                ula.triggered.connect(lambda checked, idx=s_idx: send_wallpaper_cmd(f"{idx}:unlock"))
                sm.addAction(ula)

    def _populate_audio_menu(self):
        self.audio_menu.clear()
        global_current = get_current_source()
        sources = list_audio_sources()
        screens = get_connected_screens()

        global_menu = self.audio_menu.addMenu("Global (All Screens)") if len(screens) > 1 else self.audio_menu

        auto_a = QAction("Auto (default sink monitor)", global_menu)
        auto_a.setCheckable(True)
        auto_a.setChecked(global_current == "")
        auto_a.triggered.connect(lambda: set_audio_source(""))
        global_menu.addAction(auto_a)
        global_menu.addSeparator()

        for name, desc in sources:
            a = QAction(desc, global_menu)
            a.setCheckable(True)
            a.setChecked(name == global_current)
            a.triggered.connect(lambda checked, n=name: set_audio_source(n))
            global_menu.addAction(a)

        if len(screens) > 1:
            self.audio_menu.addSeparator()
            for s in screens:
                s_idx = s["index"]
                label = s["label"]
                s_current = get_screen_audio_source(s_idx)
                sm = self.audio_menu.addMenu(f"{label} Audio")

                def_a = QAction("Use Global Setting", sm)
                def_a.setCheckable(True)
                def_a.setChecked(s_current == "")
                def_a.triggered.connect(lambda checked, idx=s_idx: set_screen_audio_source(idx, ""))
                sm.addAction(def_a)
                sm.addSeparator()

                for name, desc in sources:
                    a = QAction(desc, sm)
                    a.setCheckable(True)
                    a.setChecked(name == s_current)
                    a.triggered.connect(lambda checked, idx=s_idx, n=name: set_screen_audio_source(idx, n))
                    sm.addAction(a)

    def _update_icon(self):
        self.setIcon(load_icon(MODES[self.current_mode]["icon"]))
        self.setToolTip(f"MilkDropper — {MODES[self.current_mode]['label']}")

    def set_mode(self, mode):
        if mode == self.current_mode:
            return

        if self.current_mode == "desktop":
            plasma_set_wallpaper(ORIGINAL_WALLPAPER)
        elif self.current_mode == "standard":
            kill_projectm()

        if mode == "off":
            kill_projectm()
            plasma_set_wallpaper(ORIGINAL_WALLPAPER)
        elif mode == "desktop":
            kill_projectm()
            warn_if_not_opengl()
            plasma_set_wallpaper(PROJECTM_WALLPAPER)
            send_wallpaper_cmd("reload-audio")
        elif mode == "standard":
            plasma_set_wallpaper(ORIGINAL_WALLPAPER)
            if not start_projectm_standard():
                mode = "off"

        self.current_mode = mode
        self.mode_actions[mode].setChecked(True)
        self._update_icon()

        subprocess.Popen(
            ["notify-send", "-a", "MilkDropper",
             "-i", "milkdropper",
             "MilkDropper", MODES[mode]["label"], "-t", "1500"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )

    def on_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Left-click → random preset
            send_wallpaper_cmd("random")

    def _toggle_rgb_sync(self, checked):
        if checked:
            if self._rgb_proc and self._rgb_proc.poll() is None:
                return
            self._rgb_proc = subprocess.Popen(
                [sys.executable, RGB_SCRIPT],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            if self._rgb_proc and self._rgb_proc.poll() is None:
                self._rgb_proc.terminate()
            self._rgb_proc = None

    def quit_app(self):
        if self._rgb_proc and self._rgb_proc.poll() is None:
            self._rgb_proc.terminate()
        kill_projectm()
        if self.current_mode == "desktop":
            plasma_set_wallpaper(ORIGINAL_WALLPAPER)
        QApplication.quit()


def main():
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    app.setApplicationName("MilkDropper")
    app.setDesktopFileName("milkdropper")
    app.setWindowIcon(load_icon("milkdropper"))

    if poke_running_instance():
        print("MilkDropper is already running — opened its tray menu.")
        sys.exit(0)

    controller = TrayController()

    signal.signal(signal.SIGINT, signal.SIG_DFL)
    signal.signal(signal.SIGTERM, lambda *_: controller.quit_app())

    # Python signal handlers only run while the interpreter executes bytecode;
    # inside app.exec() Qt blocks in C and a SIGTERM could sit undelivered
    # indefinitely. This idle timer wakes the interpreter so handlers fire
    # promptly — without it, quit_app() (which restores the wallpaper) may
    # never run on logout/kill.
    heartbeat = QTimer()
    heartbeat.timeout.connect(lambda: None)
    heartbeat.start(500)

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
