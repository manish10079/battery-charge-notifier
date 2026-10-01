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

# Standard library modules that pull in OpenSSL. The application never imports
# them - verified by importing the complete object graph and inspecting
# sys.modules - and they are excluded together with libcrypto/libssl so that the
# bundle carries no library that still links against a pruned DLL. hashlib is
# deliberately kept: with _hashlib gone it simply falls back to the hash
# implementations built into the interpreter.
EXCLUDED_STDLIB = [
    "ssl",
    "_ssl",
    "_hashlib",
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
    excludes=EXCLUDED_QT_MODULES + EXCLUDED_OTHER + EXCLUDED_STDLIB,
    noarchive=False,
    optimize=0,
)

# ---------------------------------------------------------------------------
# Pruning
# ---------------------------------------------------------------------------
# The PySide6 hook collects essentially every Qt library it can find, which
# drags in whole subsystems this application never touches. Excluding the Python
# modules above does not help: the libraries arrive as binaries. Filtering them
# out here removes roughly half the bundle.
#
# Every removal is justified by "nothing in this build imports or loads it",
# which tests/test_packaging.py checks statically against the PE import tables.

#: Qt libraries that no remaining component depends on.
EXCLUDED_QT_LIBRARIES = {
    # Software OpenGL rasteriser (Mesa llvmpipe), ~7 MiB on its own. The UI is
    # drawn with the raster paint engine and never requests an OpenGL surface.
    "opengl32sw.dll",
    # QML and the Qt Quick runtime. The interface is entirely widget based.
    "Qt6Qml.dll",
    "Qt6QmlMeta.dll",
    "Qt6QmlModels.dll",
    "Qt6QmlWorkerScript.dll",
    "Qt6Quick.dll",
    # PDF rendering.
    "Qt6Pdf.dll",
    # OpenGL wrappers; nothing creates a QOpenGLWidget.
    "Qt6OpenGL.dll",
    "Qt6OpenGLWidgets.dll",
    # SVG. The bundled artwork is PNG and ICO only.
    "Qt6Svg.dll",
    # On-screen keyboard, pulled in only as an input method plugin.
    "Qt6VirtualKeyboard.dll",
    # OpenSSL. QtNetwork loads it lazily and only to negotiate TLS; the
    # single-instance gate uses QLocalSocket, which is a named pipe on Windows
    # and a Unix domain socket elsewhere, so no TLS is ever negotiated.
    "libcrypto-3.dll",
    "libcrypto-3-x64.dll",
    "libssl-3.dll",
    "libssl-3-x64.dll",
}

#: Qt plugin groups to prune, listing the file names to keep in each. An empty
#: set drops the whole group.
PRUNED_PLUGIN_GROUPS = {
    # PNG is built into QtGui; the application icon is a .ico, so qico stays.
    "imageformats": {"qico.dll"},
    # Only the native Windows plugin is used. qdirect2d, qminimal and
    # qoffscreen are alternatives chosen through QT_QPA_PLATFORM.
    "platforms": {"qwindows.dll"},
    # TLS backends exist solely for the handshake we never perform.
    "tls": set(),
    # Icon engines exist to render SVG icons.
    "iconengines": set(),
    # Only needed by QNetworkInformation, which is not used.
    "networkinformation": set(),
    # Belongs to Qt6VirtualKeyboard.
    "platforminputcontexts": set(),
}


def prune_qt(entries):  # noqa: ANN001, ANN201 - PyInstaller TOC
    """Drop bundled files that this application never loads.

    Args:
        entries: An ``Analysis`` ``binaries`` or ``datas`` table.

    Returns:
        The entries worth shipping.
    """
    kept = []
    for entry in entries:
        parts = str(entry[0]).replace("\\", "/").split("/")
        filename = parts[-1]

        if filename in EXCLUDED_QT_LIBRARIES:
            continue
        # Qt translation catalogues live in a directory beside the libraries.
        # The user-facing text is entirely this application's own.
        if "translations" in parts:
            continue
        if "plugins" in parts:
            index = parts.index("plugins")
            if index + 1 < len(parts):
                group = parts[index + 1]
                if group in PRUNED_PLUGIN_GROUPS:
                    if filename not in PRUNED_PLUGIN_GROUPS[group]:
                        continue
        kept.append(entry)
    return kept


a.binaries = prune_qt(a.binaries)
a.datas = prune_qt(a.datas)

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
