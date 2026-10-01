# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for Battery Charge Notifier.

Produces a single-file, windowed executable with the application and tray icons
bundled as package data under ``battery_charge_notifier/assets``, which is exactly where
:mod:`battery_charge_notifier.resources` looks for them inside a frozen build.

Build with::

    pyinstaller packaging/battery_charge_notifier.spec

The result is ``dist/Battery Charge Notifier.exe`` (``Battery Charge Notifier`` on macOS/Linux).
"""

from pathlib import Path

PROJECT_ROOT = Path(SPECPATH).parent
ASSETS = PROJECT_ROOT / "battery_charge_notifier" / "assets"
ENTRY_POINT = PROJECT_ROOT / "packaging" / "launcher.py"

# Qt is far larger than this application needs. Excluding the heavyweight
# modules keeps the bundle small without affecting the tray UI, which only uses
# QtCore, QtGui, QtWidgets and QtNetwork.
EXCLUDED_QT_MODULES = [
    "PySide6.Qt3DAnimation",
    "PySide6.Qt3DCore",
    "PySide6.Qt3DExtras",
    "PySide6.Qt3DInput",
    "PySide6.Qt3DLogic",
    "PySide6.Qt3DRender",
    "PySide6.QtBluetooth",
    "PySide6.QtCharts",
    "PySide6.QtDataVisualization",
    "PySide6.QtDesigner",
    "PySide6.QtHelp",
    "PySide6.QtMultimedia",
    "PySide6.QtMultimediaWidgets",
    "PySide6.QtOpenGL",
    "PySide6.QtOpenGLWidgets",
    "PySide6.QtPdf",
    "PySide6.QtPdfWidgets",
    "PySide6.QtPositioning",
    "PySide6.QtQml",
    "PySide6.QtQuick",
    "PySide6.QtQuick3D",
    "PySide6.QtQuickWidgets",
    "PySide6.QtRemoteObjects",
    "PySide6.QtScxml",
    "PySide6.QtSensors",
    "PySide6.QtSerialPort",
    "PySide6.QtSpatialAudio",
    "PySide6.QtSql",
    "PySide6.QtStateMachine",
    "PySide6.QtSvg",
    "PySide6.QtSvgWidgets",
    "PySide6.QtTest",
    "PySide6.QtTextToSpeech",
    "PySide6.QtUiTools",
    "PySide6.QtWebChannel",
    "PySide6.QtWebEngineCore",
    "PySide6.QtWebEngineWidgets",
    "PySide6.QtWebSockets",
]

# Development-only packages that must never end up in a release build.
EXCLUDED_OTHER = [
    "pytest",
    "pytestqt",
    "PyInstaller",
    "setuptools",
    "tkinter",
    "unittest",
]

a = Analysis(  # noqa: F821 - injected by PyInstaller
    [str(ENTRY_POINT)],
    pathex=[str(PROJECT_ROOT)],
    binaries=[],
    # The icons are package data; they must be present at runtime.
    datas=[(str(ASSETS), "battery_charge_notifier/assets")],
    hiddenimports=["psutil"],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=EXCLUDED_QT_MODULES + EXCLUDED_OTHER,
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)  # noqa: F821 - injected by PyInstaller

exe = EXE(  # noqa: F821 - injected by PyInstaller
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    # The executable filename has no spaces so it stays comfortable to launch
    # from a shell; the user-facing name is "Battery Charge Notifier".
    name="BatteryChargeNotifier",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    # A tray application must not open a console window. Build with
    # console=True instead when you need to watch the log output.
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(ASSETS / "app.ico"),
)
