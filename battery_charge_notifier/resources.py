"""Access to the icons bundled as package data.

Both the source checkout and the PyInstaller bundle are supported: frozen builds
unpack ``battery_charge_notifier/assets`` under ``sys._MEIPASS``, while a normal install
reads it next to this module.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

from PySide6.QtGui import QIcon, QPixmap

logger = logging.getLogger(__name__)

ASSET_DIRNAME = "assets"
PACKAGE_DIRNAME = "battery_charge_notifier"

#: Application icon used for windows and the executable.
APP_ICON = "app.ico"
APP_ICON_PNG = "app.png"

#: Tray icon variants, keyed by the situation they represent.
TRAY_OK = "tray_ok.png"
TRAY_PLUG = "tray_plug.png"
TRAY_UNPLUG = "tray_unplug.png"
TRAY_PAUSED = "tray_paused.png"

#: Spin box arrow bitmaps used by the settings dialog's style sheet.
ARROW_UP = "arrow_up.png"
ARROW_DOWN = "arrow_down.png"

_assets_cache: Path | None = None


def assets_dir() -> Path:
    """Return the directory holding the bundled assets.

    Returns:
        The first existing candidate: the PyInstaller extraction directory when
        frozen, otherwise the directory beside this module.
    """
    global _assets_cache
    if _assets_cache is not None:
        return _assets_cache

    candidates: list[Path] = []
    bundle_root = getattr(sys, "_MEIPASS", None)
    if bundle_root:
        candidates.append(Path(bundle_root) / PACKAGE_DIRNAME / ASSET_DIRNAME)
        candidates.append(Path(bundle_root) / ASSET_DIRNAME)
    candidates.append(Path(__file__).resolve().parent / ASSET_DIRNAME)

    for candidate in candidates:
        if candidate.is_dir():
            _assets_cache = candidate
            return candidate

    # Nothing exists yet (e.g. assets were never generated); report the
    # canonical location so the error message is actionable.
    _assets_cache = candidates[-1]
    return _assets_cache


def asset_path(name: str) -> Path:
    """Return the absolute path of a bundled asset.

    Args:
        name: File name such as ``"tray_ok.png"``.

    Returns:
        The path, which may not exist; callers degrade gracefully.
    """
    return assets_dir() / name


def has_asset(name: str) -> bool:
    """Return whether *name* is present in the bundle."""
    return asset_path(name).is_file()


def load_icon(name: str) -> QIcon:
    """Load a bundled icon.

    Args:
        name: File name such as ``"app.ico"``.

    Returns:
        The icon, or an empty :class:`QIcon` when the asset is missing so that a
        packaging mistake degrades to "no icon" instead of crashing.
    """
    path = asset_path(name)
    if not path.is_file():
        logger.warning("Icon asset %s is missing (looked in %s)", name, path.parent)
        return QIcon()
    return QIcon(str(path))


def load_pixmap(name: str) -> QPixmap:
    """Load a bundled pixmap.

    Args:
        name: File name such as ``"tray_plug.png"``.

    Returns:
        The pixmap, or a null :class:`QPixmap` when the asset is missing.
    """
    path = asset_path(name)
    if not path.is_file():
        logger.warning("Icon asset %s is missing (looked in %s)", name, path.parent)
        return QPixmap()
    return QPixmap(str(path))


def action_icon_name(action: str) -> str:
    """Choose the popup icon for a warning action.

    Args:
        action: ``"unplug"`` or ``"plug_in"``.

    Returns:
        A file name understood by :func:`load_icon`.
    """
    return TRAY_UNPLUG if action == "unplug" else TRAY_PLUG


__all__ = [
    "APP_ICON",
    "APP_ICON_PNG",
    "ARROW_DOWN",
    "ARROW_UP",
    "TRAY_OK",
    "TRAY_PAUSED",
    "TRAY_PLUG",
    "TRAY_UNPLUG",
    "action_icon_name",
    "asset_path",
    "assets_dir",
    "has_asset",
    "load_icon",
    "load_pixmap",
]
