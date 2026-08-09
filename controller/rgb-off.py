#!/usr/bin/env python3
"""Hold all OpenRGB devices OFF (black) via the SDK in Direct mode.

Mirrors rgb-music.py's device setup: starts/connects to the OpenRGB SDK
server, puts every device in Direct mode, pushes black, and HOLDS the
connection (Direct state only persists while a process is connected —
this is the only path that reaches the addressable fans + ROG Spotlight,
which ignore one-shot CLI hardware modes).

Requires: pip install --user openrgb-python
"""

import os
import shutil
import signal
import socket
import subprocess
import sys
import time

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    sys.exit("openrgb-python not installed. Run: pip install --user openrgb-python")

HOST = "127.0.0.1"
PORT = 6742
REPUSH_SEC = 5  # re-assert black periodically in case firmware tries to take back over

# Distro/PATH install first; the ~/Applications custom build is a fallback.
CUSTOM_BIN = os.path.expanduser("~/Applications/OpenRGB-custom")
CUSTOM_LIBS = os.path.expanduser("~/Applications/openrgb-libs")
BLACK = RGBColor(0, 0, 0)
_proc = None


def _up():
    try:
        socket.create_connection((HOST, PORT), timeout=0.3).close()
        return True
    except OSError:
        return False


def _launch():
    global _proc
    binary = shutil.which("openrgb") or shutil.which("OpenRGB")
    env = os.environ.copy()
    if not binary:
        if not os.access(CUSTOM_BIN, os.X_OK):
            return False
        binary = CUSTOM_BIN
        env["LD_LIBRARY_PATH"] = CUSTOM_LIBS + ":" + env.get("LD_LIBRARY_PATH", "")
    _proc = subprocess.Popen(
        [binary, "--server", "--server-port", str(PORT)],
        env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    for _ in range(40):
        if _up():
            time.sleep(4)  # device enumeration after port opens
            return True
        time.sleep(0.2)
    return False


def black_out(dev):
    # try Direct first (real-time, reaches fans/spotlight); fall back to per-LED black
    for m in ("Direct", "direct"):
        try:
            dev.set_mode(m)
            break
        except Exception:
            pass
    # resize addressable zones that report 0 LEDs so the write actually lands
    try:
        for z in dev.zones:
            if getattr(z, "leds_count", None) == 0 and getattr(z, "leds_max", 0):
                try:
                    z.resize(min(z.leds_max, 100))
                except Exception:
                    pass
    except Exception:
        pass
    try:
        dev.set_color(BLACK)
    except Exception:
        pass
    try:
        dev.set_colors([BLACK] * len(dev.colors))
    except Exception:
        pass


def main():
    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    if not _up():
        if not _launch():
            sys.exit("ERROR: OpenRGB server failed to start")

    client = OpenRGBClient(HOST, PORT, "RGB Off Holder")
    devs = client.devices
    print(f"Connected — {len(devs)} device(s); blacking out", file=sys.stderr)
    for d in devs:
        black_out(d)

    while True:
        time.sleep(REPUSH_SEC)
        for d in devs:
            try:
                d.set_color(BLACK)
            except Exception:
                pass


if __name__ == "__main__":
    main()
