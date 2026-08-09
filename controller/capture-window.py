#!/usr/bin/env python3
"""Capture projectMSDL's XWayland window via GStreamer and output to PipeWire.

Creates a PipeWire Video/Source node named 'projectm-capture' that can be
consumed by the QML wallpaper plugin via PipeWireSourceItem.

Also serves the PipeWire node_id over HTTP so the QML plugin can discover it.
"""

import json
import os
import signal
import subprocess
import sys
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 19816, not 19815: audio-fft.py owns 19815 and both can be running at once.
PORT = 19816
_node_id = 0
_lock = threading.Lock()


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        with _lock:
            nid = _node_id
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(json.dumps({"nodeId": nid}).encode())

    def log_message(self, *args):
        pass


def run_http():
    HTTPServer(("127.0.0.1", PORT), Handler).serve_forever()


def find_projectm_wid():
    """Wait for projectMSDL window to appear, return X window ID."""
    for _ in range(40):  # 10 seconds
        result = subprocess.run(
            ["xdotool", "search", "--classname", "projectMSDL"],
            capture_output=True, text=True,
        )
        wids = [w for w in result.stdout.strip().splitlines() if w]
        if wids:
            return wids[0]
        time.sleep(0.25)
    return None


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True)


def hide_window(wid):
    """Move projectMSDL off-screen so it's not visible or interactive, but still renders."""
    # Skip taskbar/pager/switcher, keep below everything
    run(f"xprop -id {wid} -f _NET_WM_STATE 32a -set _NET_WM_STATE "
        f"_NET_WM_STATE_BELOW,_NET_WM_STATE_SKIP_TASKBAR,"
        f"_NET_WM_STATE_SKIP_PAGER,_KDE_NET_WM_STATE_SKIP_SWITCHER")
    # Remove border
    run(f"xprop -id {wid} -f _MOTIF_WM_HINTS 32c -set _MOTIF_WM_HINTS '2, 0, 0, 0, 0'")
    # Move off-screen — still renders at full opacity for ximagesrc
    run(f"xdotool windowmove {wid} -4000 -4000")


def find_pw_node_id(name="projectm-capture"):
    """Find PipeWire node ID by name."""
    result = subprocess.run(["pw-dump"], capture_output=True, text=True)
    try:
        nodes = json.loads(result.stdout)
        for n in nodes:
            props = n.get("info", {}).get("props", {})
            if props.get("node.name") == name:
                return n["id"]
    except (json.JSONDecodeError, KeyError):
        pass
    return 0


def main():
    global _node_id

    signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))

    # Start HTTP server
    threading.Thread(target=run_http, daemon=True).start()

    # Wait for projectMSDL window
    wid = find_projectm_wid()
    if not wid:
        print("projectMSDL window not found", file=sys.stderr)
        sys.exit(1)

    # Start GStreamer capture pipeline
    gst_proc = subprocess.Popen([
        "gst-launch-1.0",
        "ximagesrc", f"xid={wid}", "use-damage=false",
        "!", "video/x-raw,framerate=30/1",
        "!", "queue",
        "!", "videoconvert",
        "!", "pipewiresink",
        "stream-properties=properties,media.class=Video/Source,node.name=projectm-capture",
    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    # Wait for PipeWire node to appear, then hide the window
    for _ in range(20):
        time.sleep(0.25)
        nid = find_pw_node_id()
        if nid:
            with _lock:
                _node_id = nid
            print(f"PipeWire node_id: {nid}", flush=True)
            # Hide the projectMSDL window — still renders for capture
            hide_window(wid)
            break

    # Keep alive until killed
    try:
        gst_proc.wait()
    except KeyboardInterrupt:
        gst_proc.terminate()


if __name__ == "__main__":
    main()
