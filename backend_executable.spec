# backend_executable.spec
# -- mode: python ; coding: utf-8 --

from PyInstaller.utils.hooks import collect_submodules

# --- Hidden Imports ---
# This tells PyInstaller to include modules that it cannot find on its own.
# We collect ALL submodules from 'eventlet' and 'dns' to prevent ModuleNotFoundError.
# Also including all other dependencies from requirements.txt to be safe.
hidden_imports = [
    'eventlet',
    'greenlet',
    'dns',
    'flask',
    'flask_cors',
    'flask_socketio',
    'engineio',
    'socketio',
    'numpy',
    'scipy',
    'mne',
    'dotenv',
    'websocket',
    'websockets',
    'logging.config',
]
hidden_imports = [mod for lib in hidden_imports for mod in collect_submodules(lib)]

a = Analysis(
    ['run_backend.py'],
    pathex=[],
    binaries=[],
    datas=[('backend', 'backend')],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='backend_executable',
    debug=False,
    bootloader_ignore_signals=False,
    strip=True,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=True,
    upx=False,
    upx_exclude=[],
    name='backend_executable',
)