import sys
from pathlib import Path

def base_path():
    """Return the base path for resources that works both when running
    as a script and when bundled by PyInstaller (sys.frozen)."""
    if getattr(sys, 'frozen', False):
        return Path(sys._MEIPASS)
    return Path(__file__).parent
