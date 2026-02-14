"""
Centralizes logic for determining application paths.
Ensures compatibility between development mode (script)
and frozen mode (PyInstaller).
"""

import os
import sys
from pathlib import Path

from platformdirs import user_data_path, user_documents_path


def get_assets_dir() -> Path:
    """
    Returns the directory containing bundled assets (read-only).
    Used for: locales, commands.json, default configs.
    """
    if getattr(sys, "frozen", False):
        # In PyInstaller, static assets are in sys._MEIPASS
        # pylint: disable=protected-access
        return Path(sys._MEIPASS)  # type: ignore

    # In dev mode, assets are relative to this file
    return Path(__file__).resolve().parent.parent.parent


def get_user_data_dir() -> Path:
    """
    Returns the directory for writable user data.
    Used for: Database, Logs, User Configs.
    """
    if getattr(sys, "frozen", False) or "__compiled__" in globals():
        # In frozen mode, use permanent user data directory
        return user_data_path("sd-cpp-gui")

    # In dev mode, put data in the project root
    return Path(__file__).resolve().parent.parent.parent


def get_output_dir() -> Path:
    """
    Returns the default output directory.
    """
    return user_documents_path() / "SD-GUI"


# Read-only assets (Bundled)
ASSETS_DIR = get_assets_dir()
# We assume commands.json and locales are bundled inside a 'data'
# folder in the source
# You must ensure your .spec file adds: datas=[('data', 'data')]
COMMANDS_FILE = ASSETS_DIR / "data" / "commands.json"
LOCALES_DIR = ASSETS_DIR / "data" / "locales"
AUTOCOMPLETE_FILE = ASSETS_DIR / "data" / "autocomplete.db"

# Writable user data
ROOT_DIR = get_user_data_dir()
DATA_DIR = ROOT_DIR / "data"
DB_FILE = DATA_DIR / "app_data.sqlite"
LOGS_DIR = ROOT_DIR / "logs"

OUTPUT_DIR = get_output_dir()

# Ensure writable directories exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)
os.makedirs(LOGS_DIR, exist_ok=True)
