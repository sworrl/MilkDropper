#!/usr/bin/env python3
"""Capture system audio via PipeWire monitor, compute FFT, serve JSON over HTTP for QML."""

import json
import time
import os
import signal
import sys
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import numpy as np

PORT = 19815
BANDS = 64
SAMPLE_RATE = 44100
CHUNK = 1024

# Shared state for HTTP server
_current_json = b'{"bass":0,"mid":0,"treble":0}'
_lock = threading.Lock()


class FFTHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        with _lock:
            data = _current_json
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *args):
        pass  # silence request logs


def detect_source():
    """Explicit source from env, or the default sink's monitor."""
    source = os.environ.get("PROJECTM_AUDIO_SOURCE", "")
    if not source:
        try:
            sink = subprocess.check_output(
                ["pactl", "get-default-sink"], text=True
            ).strip()
            source = sink + ".monitor"
        except Exception:
            source = ""
    return source


def start_parec():
    cmd = [
        "parec",
        "--format=float32le",
        "--rate=" + str(SAMPLE_RATE),
        "--channels=1",
    ]
    source = detect_source()
    if source:
        cmd += ["-d", source]
    try:
        return subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
        )
    except FileNotFoundError:
        sys.exit("audio-fft: parec not found — install pulseaudio-utils")


def main():
    global _current_json

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Bind in the main thread so a taken port is a hard error, not a silently
    # dead daemon thread with the rest of the script running serverless.
    try:
        server = HTTPServer(("127.0.0.1", PORT), FFTHandler)
    except OSError as e:
        sys.exit(f"audio-fft: cannot bind 127.0.0.1:{PORT}: {e}")
    threading.Thread(target=server.serve_forever, daemon=True).start()

    proc = start_parec()
    spawned = time.monotonic()
    fast_failures = 0

    try:
        while True:
            raw = proc.stdout.read(CHUNK * 4)
            if len(raw) < CHUNK * 4:
                # EOF: parec died (device unplugged, default sink changed,
                # pipewire restarted). Respawn it — re-detecting the source —
                # instead of spinning forever on stale data.
                proc.wait()
                if time.monotonic() - spawned < 2.0:
                    fast_failures += 1
                    if fast_failures >= 5:
                        sys.exit("audio-fft: parec keeps dying immediately "
                                 "— is PulseAudio/PipeWire running?")
                else:
                    fast_failures = 0
                time.sleep(1.0)
                proc = start_parec()
                spawned = time.monotonic()
                continue

            samples = np.frombuffer(raw, dtype=np.float32)

            fft = np.abs(np.fft.rfft(samples * np.hanning(len(samples))))
            fft = fft[:BANDS]
            fft = np.clip(fft / (CHUNK * 0.05), 0.0, 1.0)

            third = max(1, len(fft) // 3)
            bass = float(np.mean(fft[:third]))
            mid = float(np.mean(fft[third : 2 * third]))
            treble = float(np.mean(fft[2 * third :]))

            data = json.dumps(
                {"bass": round(bass, 4), "mid": round(mid, 4), "treble": round(treble, 4)},
                separators=(",", ":"),
            ).encode()

            with _lock:
                _current_json = data

    except (BrokenPipeError, KeyboardInterrupt):
        pass
    finally:
        proc.terminate()


if __name__ == "__main__":
    main()
