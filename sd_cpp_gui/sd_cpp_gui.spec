# -*- mode: python ; coding: utf-8 -*-

from PyInstaller.utils.hooks import collect_submodules, collect_data_files
import sys
import os

block_cipher = None

# -----------------------------------------------------------------------------
# 1. SETUP PATHS & IMPORTS
# -----------------------------------------------------------------------------

hidden_imports = []
hidden_imports += collect_submodules("sd_cpp_gui.plugins")

hidden_imports += [
    "PIL.ImageTk",
    "PIL._tkinter_finder",
    "tkinter",
    "ttkbootstrap",
    "peewee",
    "playhouse.sqlite_ext",
    "yaml",
    "toml",
]

# -----------------------------------------------------------------------------
# 2. COLLECT DATA FILES
# -----------------------------------------------------------------------------

datas = []
if os.path.exists("../data"):
    datas.append(("../data", "data"))
else:
    print(
        "WARNING: 'data' folder not found in project root. Assets will be missing."
    )

datas += collect_data_files("ttkbootstrap")

# -----------------------------------------------------------------------------
# 3. ANALYSIS
# -----------------------------------------------------------------------------

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

# -----------------------------------------------------------------------------
# 4. EXE (One-File Bundle)
# -----------------------------------------------------------------------------

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="SD-CPP-GUI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon='assets/icon.ico',
)
