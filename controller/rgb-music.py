#!/usr/bin/env python3
"""Audio-reactive RGB lighting via OpenRGB SDK.

Reads bass/mid/treble from audio-fft.py (port 19815) and drives all
OpenRGB devices in real-time sync with the music.

Requires: pip install --user openrgb-python
"""

import atexit
import json
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.request

try:
    from openrgb import OpenRGBClient
    from openrgb.utils import RGBColor
except ImportError:
    sys.exit("openrgb-python not installed. Run: pip install --user openrgb-python")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FFT_SCRIPT = os.path.join(SCRIPT_DIR, "audio-fft.py")
FFT_HOST = "127.0.0.1"
FFT_PORT = 19815
FFT_URL = f"http://{FFT_HOST}:{FFT_PORT}/"
OPENRGB_HOST = "127.0.0.1"
OPENRGB_PORT = 6742
FPS = 30
SMOOTH = 0.4   # 0=no response, 1=instantaneous
GAIN = 2.5     # amplify signal; audio levels are often quiet

# Distro/PATH install first; the ~/Applications custom build is a fallback.
OPENRGB_CUSTOM_BIN = os.path.expanduser("~/Applications/OpenRGB-custom")
OPENRGB_CUSTOM_LIBS = os.path.expanduser("~/Applications/openrgb-libs")

_server_proc = None
_fft_proc = None


def _port_open(host, port):
    try:
        s = socket.create_connection((host, port), timeout=0.3)
        s.close()
        return True
    except OSError:
        return False


def _is_server_up():
    return _port_open(OPENRGB_HOST, OPENRGB_PORT)


def _find_openrgb():
    binary = shutil.which("openrgb") or shutil.which("OpenRGB")
    if binary:
        return binary, None
    if os.access(OPENRGB_CUSTOM_BIN, os.X_OK):
        return OPENRGB_CUSTOM_BIN, OPENRGB_CUSTOM_LIBS
    return None, None


def _launch_server():
    global _server_proc
    binary, libs = _find_openrgb()
    if not binary:
        return False
    env = os.environ.copy()
    if libs:
        env["LD_LIBRARY_PATH"] = libs + ":" + env.get("LD_LIBRARY_PATH", "")
    _server_proc = subprocess.Popen(
        [binary, "--server", "--server-port", str(OPENRGB_PORT)],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(30):
        if _is_server_up():
            time.sleep(4)  # wait for device enumeration after port opens
            return True
        time.sleep(0.2)
    _server_proc.terminate()
    return False


def _stop_fft():
    if _fft_proc and _fft_proc.poll() is None:
        _fft_proc.terminate()
        try:
            _fft_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _fft_proc.kill()


def _ensure_fft_server():
    """audio-fft.py supplies the band data; nothing else starts it, so without
    this the loop would sync the lights to permanent silence."""
    global _fft_proc
    if _port_open(FFT_HOST, FFT_PORT):
        return True
    if not os.path.isfile(FFT_SCRIPT):
        print(f"audio-fft.py not found at {FFT_SCRIPT}", file=sys.stderr)
        return False
    _fft_proc = subprocess.Popen(
        [sys.executable, FFT_SCRIPT],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    atexit.register(_stop_fft)
    for _ in range(25):
        if _port_open(FFT_HOST, FFT_PORT):
            return True
        if _fft_proc.poll() is not None:
            break
        time.sleep(0.2)
    print("audio-fft.py failed to start (numpy/parec missing?)", file=sys.stderr)
    return False


def _stop_server():
    if _server_proc and _server_proc.poll() is None:
        _server_proc.terminate()
        try:
            _server_proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            _server_proc.kill()


def fetch_audio():
    try:
        with urllib.request.urlopen(FFT_URL, timeout=0.04) as resp:
            return json.loads(resp.read())
    except Exception:
        return {"bass": 0.0, "mid": 0.0, "treble": 0.0}


def bands_to_color(bass, mid, treble):
    """bass=red, mid=green, treble=blue"""
    r = min(255, int(bass   * 255 * GAIN))
    g = min(255, int(mid    * 255 * GAIN))
    b = min(255, int(treble * 255 * GAIN))
    return RGBColor(r, g, b)


def try_set_direct(dev):
    for name in ("Direct", "direct"):
        try:
            dev.set_mode(name)
            return True
        except Exception:
            pass
    return False


def main():
    signal.signal(signal.SIGINT,  lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    if not _ensure_fft_server():
        sys.exit("ERROR: no audio FFT source — cannot sync to music")

    if not _is_server_up():
        print("Starting OpenRGB server...", file=sys.stderr)
        if not _launch_server():
            sys.exit("ERROR: OpenRGB server failed to start "
                     "(no openrgb in PATH or ~/Applications/OpenRGB-custom)")
        atexit.register(_stop_server)
        print("OpenRGB server ready.", file=sys.stderr)

    try:
        client = OpenRGBClient(OPENRGB_HOST, OPENRGB_PORT, "MilkDropper RGB Sync")
    except ConnectionRefusedError:
        sys.exit("ERROR: Cannot connect to OpenRGB server")

    devices = client.devices
    print(f"Connected — {len(devices)} device(s)", file=sys.stderr)

    direct_devs = []
    for dev in devices:
        if try_set_direct(dev):
            direct_devs.append(dev)
            print(f"  [direct] {dev.name}", file=sys.stderr)
        else:
            print(f"  [skip]   {dev.name} (no Direct mode)", file=sys.stderr)

    if not direct_devs:
        sys.exit("No devices support Direct mode")

    def restore():
        print("Restoring Spectrum Cycle...", file=sys.stderr)
        for dev in direct_devs:
            for name in ("Spectrum Cycle", "spectrum_cycle", "Rainbow", "Static"):
                try:
                    dev.set_mode(name)
                    break
                except Exception:
                    pass

    atexit.register(restore)

    bass_s = mid_s = treble_s = 0.0
    frame_dt = 1.0 / FPS

    try:
        while True:
            t0 = time.monotonic()

            d = fetch_audio()
            bass_s   += SMOOTH * (d.get("bass",   0.0) - bass_s)
            mid_s    += SMOOTH * (d.get("mid",    0.0) - mid_s)
            treble_s += SMOOTH * (d.get("treble", 0.0) - treble_s)

            color = bands_to_color(bass_s, mid_s, treble_s)
            for dev in direct_devs:
                try:
                    dev.set_color(color)
                except Exception:
                    pass

            sleep = frame_dt - (time.monotonic() - t0)
            if sleep > 0:
                time.sleep(sleep)
    except SystemExit:
        pass


if __name__ == "__main__":
    main()
