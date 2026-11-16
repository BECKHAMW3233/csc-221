"""Path helpers that work both as normal Python and inside a PyInstaller .exe.

PyInstaller unpacks bundled files (databases, templates) into a temporary
folder exposed as sys._MEIPASS. That folder is deleted when the program
closes, so anything the program *writes* (CSV output, logs) goes next to
the .exe instead.
"""

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent


def is_frozen():
    """Return True when running from a PyInstaller-built executable."""
    return getattr(sys, "frozen", False)


def resource_path(*parts):
    """Return the path to a read-only bundled file (db, xlsx, templates)."""
    base = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
    return base.joinpath(*parts)


def writable_path(*parts):
    """Return a path for files the program creates (output CSVs, logs)."""
    base = Path(sys.executable).resolve().parent if is_frozen() else PROJECT_ROOT
    return base.joinpath(*parts)
