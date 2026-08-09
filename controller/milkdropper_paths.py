#!/usr/bin/env python3
"""Shared path discovery for MilkDropper.

Mirrors the discovery order implemented in the C++ QML plugin, so the tray
controller and the wallpaper renderer always agree on where things live:

  1. environment variable override
  2. ~/.config/milkdropper/milkdropper.conf  ([Paths] section)
  3. well-known install locations

Nothing here may be hardcoded to a single machine — the same files ship in a
.deb that other people install.
"""

import configparser
import os
import shutil

HOME = os.path.expanduser("~")
CONFIG_FILE = os.path.join(
    os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config")),
    "milkdropper", "milkdropper.conf",
)


def _config():
    parser = configparser.ConfigParser()
    try:
        parser.read(CONFIG_FILE)
    except (configparser.Error, OSError):
        return {}
    return dict(parser["Paths"]) if parser.has_section("Paths") else {}


def _configured(key):
    # ConfigParser lowercases keys; the C++ side writes them capitalised.
    return _config().get(key.lower(), "")


def _first(candidates, test):
    for c in candidates:
        if c and test(c):
            return c
    return ""


def data_dirs():
    """XDG data dirs, most specific first."""
    dirs = [os.environ.get("XDG_DATA_HOME", os.path.join(HOME, ".local/share"))]
    dirs += os.environ.get("XDG_DATA_DIRS", "/usr/local/share:/usr/share").split(":")
    return [d.rstrip("/") for d in dirs if d]


def find_projectmsdl():
    """Locate the projectMSDL binary, or "" if it isn't installed."""
    candidates = [
        os.environ.get("MILKDROPPER_PROJECTMSDL", ""),
        _configured("ProjectMSDL"),
        shutil.which("projectMSDL") or "",
        f"{HOME}/.local/share/Steam/steamapps/common/projectM/projectMSDL",
        f"{HOME}/.steam/steam/steamapps/common/projectM/projectMSDL",
        f"{HOME}/.var/app/com.valvesoftware.Steam/data/Steam/steamapps/common/projectM/projectMSDL",
        "/usr/bin/projectMSDL",
        "/usr/local/bin/projectMSDL",
    ]
    return _first(candidates, lambda p: os.path.isfile(p) and os.access(p, os.X_OK))


def find_presets():
    candidates = [
        os.environ.get("MILKDROPPER_PRESET_PATH", ""),
        _configured("Presets"),
        f"{HOME}/.local/share/milkdropper/presets",
        f"{HOME}/.local/share/Steam/steamapps/common/projectM/presets",
        f"{HOME}/.steam/steam/steamapps/common/projectM/presets",
    ] + [f"{d}/milkdropper/presets" for d in data_dirs()] \
      + [f"{d}/projectM/presets" for d in data_dirs()]
    return _first(candidates, os.path.isdir)


def find_textures():
    candidates = [
        os.environ.get("MILKDROPPER_TEXTURE_PATH", ""),
        _configured("Textures"),
        f"{HOME}/.local/share/milkdropper/textures",
        f"{HOME}/.local/share/Steam/steamapps/common/projectM/textures",
        f"{HOME}/.steam/steam/steamapps/common/projectM/textures",
    ] + [f"{d}/milkdropper/textures" for d in data_dirs()] \
      + [f"{d}/projectM/textures" for d in data_dirs()]
    return _first(candidates, os.path.isdir)


def find_pipedreams():
    """Locate the PipeDreams launcher (sister project), or "" if not installed."""
    candidates = [
        os.environ.get("MILKDROPPER_PIPEDREAMS", ""),
        _configured("PipeDreams"),
        shutil.which("pipedreams") or "",
        "/usr/local/bin/pipedreams",
        "/usr/bin/pipedreams",
        f"{HOME}/.local/bin/pipedreams",
    ]
    return _first(candidates, lambda p: os.path.isfile(p) and os.access(p, os.X_OK))


if __name__ == "__main__":
    print(f"config:     {CONFIG_FILE}{'' if os.path.exists(CONFIG_FILE) else ' (absent)'}")
    print(f"projectMSDL: {find_projectmsdl() or '(not found)'}")
    print(f"presets:     {find_presets() or '(not found)'}")
    print(f"textures:    {find_textures() or '(not found)'}")
    print(f"pipedreams:  {find_pipedreams() or '(not found)'}")
