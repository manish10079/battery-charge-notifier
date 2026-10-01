"""Fluent Design tokens for Battery Charge Notifier.

This module is the **only** place in the codebase where a colour literal may
appear. Every widget, style sheet and generated icon pulls its colours from the
named tokens below.

Two complete palettes exist - Fluent Light (Windows 11 default) and Fluent Dark.
:func:`apply_theme` copies the active palette onto the module-level names that
the rest of the package imports, so existing call sites keep working.

Qt style sheets expect ``rgba()`` alpha in the 0-255 range, so the 0-1 alphas
from the design spec are converted here.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Literal

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication, QWidget

ThemeName = Literal["light", "dark"]


@dataclass(frozen=True)
class Palette:
    """One complete Fluent theme.

    Attribute names match the module-level tokens the rest of the package uses.
    """

    SURFACE: str
    SURFACE_CONTAINER_LOW: str
    SURFACE_CONTAINER: str
    SURFACE_CONTAINER_HIGH: str
    SURFACE_OVERLAY: str
    SCRIM: str
    SCRIM_SOFT: str
    OUTLINE: str
    OUTLINE_STRONG: str
    TEXT_PRIMARY: str
    TEXT_SECONDARY: str
    TEXT_MUTED: str
    TEXT_ON_ACCENT: str
    ACCENT_UNPLUG: str
    ACCENT_UNPLUG_DIM: str
    ACCENT_UNPLUG_SOFT: str
    ACCENT_PLUG: str
    ACCENT_PLUG_DIM: str
    ACCENT_PLUG_SOFT: str
    ACCENT_PRIMARY: str
    ACCENT_PRIMARY_DIM: str
    ACCENT_PRIMARY_SOFT: str
    ACCENT_OK: str
    GAUGE_TRACK: str
    GAUGE_TICK: str
    GAUGE_TICK_MAJOR: str
    BUTTON_BACKGROUND: str
    BUTTON_BACKGROUND_HOVER: str
    BUTTON_BACKGROUND_PRESSED: str
    BUTTON_TEXT: str
    INPUT_BACKGROUND: str
    INPUT_BORDER: str
    INPUT_BORDER_FOCUS: str
    INPUT_INVALID_BORDER: str
    FIELD_LABEL: str
    FIELD_HELP: str
    FIELD_ERROR: str
    SCROLLBAR_HANDLE: str
    SCROLLBAR_HANDLE_HOVER: str
    ICON_BACKGROUND: str
    ICON_FOREGROUND: str
    CONTROL_FILL: str
    CONTROL_FILL_HOVER: str
    CONTROL_FILL_PRESSED: str
    CONTROL_FILL_DISABLED: str
    ACCENT_BAR: str
    FOCUS_OUTER: str
    SHADOW: str


LIGHT = Palette(
    SURFACE="#F3F3F3",
    SURFACE_CONTAINER_LOW="#F3F3F3",
    SURFACE_CONTAINER="#FFFFFF",
    SURFACE_CONTAINER_HIGH="#F9F9F9",
    SURFACE_OVERLAY="#FFFFFF",
    SCRIM="#FFFFFF",
    SCRIM_SOFT="rgba(255, 255, 255, 242)",
    OUTLINE="rgba(0, 0, 0, 20)",
    OUTLINE_STRONG="rgba(0, 0, 0, 31)",
    TEXT_PRIMARY="rgba(0, 0, 0, 230)",
    TEXT_SECONDARY="rgba(0, 0, 0, 156)",
    TEXT_MUTED="rgba(0, 0, 0, 97)",
    TEXT_ON_ACCENT="#FFFFFF",
    ACCENT_UNPLUG="#C65D00",
    ACCENT_UNPLUG_DIM="#9A4A00",
    ACCENT_UNPLUG_SOFT="rgba(198, 93, 0, 38)",
    ACCENT_PLUG="#C42B1C",
    ACCENT_PLUG_DIM="#9A2218",
    ACCENT_PLUG_SOFT="rgba(196, 43, 28, 38)",
    ACCENT_PRIMARY="#005FB8",
    ACCENT_PRIMARY_DIM="#0052A3",
    ACCENT_PRIMARY_SOFT="rgba(0, 95, 184, 38)",
    ACCENT_OK="#0F7B0F",
    GAUGE_TRACK="#E6E6E6",
    GAUGE_TICK="rgba(0, 0, 0, 97)",
    GAUGE_TICK_MAJOR="rgba(0, 0, 0, 156)",
    BUTTON_BACKGROUND="rgba(255, 255, 255, 178)",
    BUTTON_BACKGROUND_HOVER="rgba(249, 249, 249, 128)",
    BUTTON_BACKGROUND_PRESSED="rgba(249, 249, 249, 77)",
    BUTTON_TEXT="rgba(0, 0, 0, 230)",
    INPUT_BACKGROUND="rgba(255, 255, 255, 178)",
    INPUT_BORDER="rgba(0, 0, 0, 31)",
    INPUT_BORDER_FOCUS="#005FB8",
    INPUT_INVALID_BORDER="#C42B1C",
    FIELD_LABEL="rgba(0, 0, 0, 230)",
    FIELD_HELP="rgba(0, 0, 0, 156)",
    FIELD_ERROR="#C42B1C",
    SCROLLBAR_HANDLE="rgba(0, 0, 0, 56)",
    SCROLLBAR_HANDLE_HOVER="rgba(0, 0, 0, 92)",
    ICON_BACKGROUND="#F3F3F3",
    ICON_FOREGROUND="#1A1A1A",
    CONTROL_FILL="rgba(255, 255, 255, 178)",
    CONTROL_FILL_HOVER="rgba(249, 249, 249, 128)",
    CONTROL_FILL_PRESSED="rgba(249, 249, 249, 77)",
    CONTROL_FILL_DISABLED="rgba(249, 249, 249, 77)",
    ACCENT_BAR="#005FB8",
    FOCUS_OUTER="#005FB8",
    SHADOW="rgba(0, 0, 0, 38)",
)

DARK = Palette(
    SURFACE="#202020",
    SURFACE_CONTAINER_LOW="#202020",
    SURFACE_CONTAINER="#2D2D2D",
    SURFACE_CONTAINER_HIGH="#323232",
    SURFACE_OVERLAY="#373737",
    SCRIM="#2D2D2D",
    SCRIM_SOFT="rgba(45, 45, 45, 242)",
    OUTLINE="rgba(255, 255, 255, 20)",
    OUTLINE_STRONG="rgba(255, 255, 255, 31)",
    TEXT_PRIMARY="#FFFFFF",
    TEXT_SECONDARY="rgba(255, 255, 255, 199)",
    TEXT_MUTED="rgba(255, 255, 255, 92)",
    TEXT_ON_ACCENT="#000000",
    ACCENT_UNPLUG="#FF9E43",
    ACCENT_UNPLUG_DIM="#C47A30",
    ACCENT_UNPLUG_SOFT="rgba(255, 158, 67, 51)",
    ACCENT_PLUG="#FF6B6B",
    ACCENT_PLUG_DIM="#C45454",
    ACCENT_PLUG_SOFT="rgba(255, 107, 107, 51)",
    ACCENT_PRIMARY="#60CDFF",
    ACCENT_PRIMARY_DIM="#67D3FF",
    ACCENT_PRIMARY_SOFT="rgba(96, 205, 255, 38)",
    ACCENT_OK="#6CCB5F",
    GAUGE_TRACK="#1A1A1A",
    GAUGE_TICK="rgba(255, 255, 255, 92)",
    GAUGE_TICK_MAJOR="rgba(255, 255, 255, 156)",
    BUTTON_BACKGROUND="rgba(255, 255, 255, 15)",
    BUTTON_BACKGROUND_HOVER="rgba(255, 255, 255, 23)",
    BUTTON_BACKGROUND_PRESSED="rgba(255, 255, 255, 10)",
    BUTTON_TEXT="#FFFFFF",
    INPUT_BACKGROUND="rgba(255, 255, 255, 15)",
    INPUT_BORDER="rgba(255, 255, 255, 31)",
    INPUT_BORDER_FOCUS="#60CDFF",
    INPUT_INVALID_BORDER="#FF6B6B",
    FIELD_LABEL="#FFFFFF",
    FIELD_HELP="rgba(255, 255, 255, 199)",
    FIELD_ERROR="#FF6B6B",
    SCROLLBAR_HANDLE="rgba(255, 255, 255, 56)",
    SCROLLBAR_HANDLE_HOVER="rgba(255, 255, 255, 92)",
    ICON_BACKGROUND="#202020",
    ICON_FOREGROUND="#FFFFFF",
    CONTROL_FILL="rgba(255, 255, 255, 15)",
    CONTROL_FILL_HOVER="rgba(255, 255, 255, 23)",
    CONTROL_FILL_PRESSED="rgba(255, 255, 255, 10)",
    CONTROL_FILL_DISABLED="rgba(255, 255, 255, 5)",
    ACCENT_BAR="#60CDFF",
    FOCUS_OUTER="#60CDFF",
    SHADOW="rgba(0, 0, 0, 92)",
)

TRANSPARENT: str = "transparent"

_active: ThemeName = "light"

# Module-level aliases. Populated from LIGHT so importers always see strings.
SURFACE = LIGHT.SURFACE
SURFACE_CONTAINER_LOW = LIGHT.SURFACE_CONTAINER_LOW
SURFACE_CONTAINER = LIGHT.SURFACE_CONTAINER
SURFACE_CONTAINER_HIGH = LIGHT.SURFACE_CONTAINER_HIGH
SURFACE_OVERLAY = LIGHT.SURFACE_OVERLAY
SCRIM = LIGHT.SCRIM
SCRIM_SOFT = LIGHT.SCRIM_SOFT
OUTLINE = LIGHT.OUTLINE
OUTLINE_STRONG = LIGHT.OUTLINE_STRONG
TEXT_PRIMARY = LIGHT.TEXT_PRIMARY
TEXT_SECONDARY = LIGHT.TEXT_SECONDARY
TEXT_MUTED = LIGHT.TEXT_MUTED
TEXT_ON_ACCENT = LIGHT.TEXT_ON_ACCENT
ACCENT_UNPLUG = LIGHT.ACCENT_UNPLUG
ACCENT_UNPLUG_DIM = LIGHT.ACCENT_UNPLUG_DIM
ACCENT_UNPLUG_SOFT = LIGHT.ACCENT_UNPLUG_SOFT
ACCENT_PLUG = LIGHT.ACCENT_PLUG
ACCENT_PLUG_DIM = LIGHT.ACCENT_PLUG_DIM
ACCENT_PLUG_SOFT = LIGHT.ACCENT_PLUG_SOFT
ACCENT_PRIMARY = LIGHT.ACCENT_PRIMARY
ACCENT_PRIMARY_DIM = LIGHT.ACCENT_PRIMARY_DIM
ACCENT_PRIMARY_SOFT = LIGHT.ACCENT_PRIMARY_SOFT
ACCENT_OK = LIGHT.ACCENT_OK
GAUGE_TRACK = LIGHT.GAUGE_TRACK
GAUGE_TICK = LIGHT.GAUGE_TICK
GAUGE_TICK_MAJOR = LIGHT.GAUGE_TICK_MAJOR
BUTTON_BACKGROUND = LIGHT.BUTTON_BACKGROUND
BUTTON_BACKGROUND_HOVER = LIGHT.BUTTON_BACKGROUND_HOVER
BUTTON_BACKGROUND_PRESSED = LIGHT.BUTTON_BACKGROUND_PRESSED
BUTTON_TEXT = LIGHT.BUTTON_TEXT
INPUT_BACKGROUND = LIGHT.INPUT_BACKGROUND
INPUT_BORDER = LIGHT.INPUT_BORDER
INPUT_BORDER_FOCUS = LIGHT.INPUT_BORDER_FOCUS
INPUT_INVALID_BORDER = LIGHT.INPUT_INVALID_BORDER
FIELD_LABEL = LIGHT.FIELD_LABEL
FIELD_HELP = LIGHT.FIELD_HELP
FIELD_ERROR = LIGHT.FIELD_ERROR
SCROLLBAR_HANDLE = LIGHT.SCROLLBAR_HANDLE
SCROLLBAR_HANDLE_HOVER = LIGHT.SCROLLBAR_HANDLE_HOVER
ICON_BACKGROUND = LIGHT.ICON_BACKGROUND
ICON_FOREGROUND = LIGHT.ICON_FOREGROUND
CONTROL_FILL = LIGHT.CONTROL_FILL
CONTROL_FILL_HOVER = LIGHT.CONTROL_FILL_HOVER
CONTROL_FILL_PRESSED = LIGHT.CONTROL_FILL_PRESSED
CONTROL_FILL_DISABLED = LIGHT.CONTROL_FILL_DISABLED
ACCENT_BAR = LIGHT.ACCENT_BAR
FOCUS_OUTER = LIGHT.FOCUS_OUTER
SHADOW = LIGHT.SHADOW


def current_theme() -> ThemeName:
    """Return the name of the palette currently copied onto the module tokens."""
    return _active


def palette_for(name: ThemeName) -> Palette:
    """Return the frozen palette named *name*."""
    return DARK if name == "dark" else LIGHT


def detect_system_theme(widget: QWidget | QApplication | None = None) -> ThemeName:
    """Infer light or dark from the Qt palette of *widget* or the application.

    Args:
        widget: Any widget or the ``QApplication``. ``None`` uses the app.

    Returns:
        ``"dark"`` when the window colour is closer to black than white.
    """
    app = widget if isinstance(widget, QApplication) else QApplication.instance()
    source = widget if isinstance(widget, QWidget) else app
    if source is None:
        return "light"
    color = source.palette().color(QPalette.ColorRole.Window)
    return "dark" if color.lightness() < 128 else "light"


def apply_theme(name: ThemeName) -> None:
    """Copy *name*'s palette onto the module-level token names.

    Args:
        name: ``"light"`` or ``"dark"``.
    """
    global _active
    _active = name
    module = globals()
    for field in fields(Palette):
        module[field.name] = getattr(palette_for(name), field.name)


def apply_system_theme(widget: QWidget | QApplication | None = None) -> ThemeName:
    """Detect the OS theme and apply it.

    Args:
        widget: Palette source; ``None`` uses the running application.

    Returns:
        The theme that was applied.
    """
    name = detect_system_theme(widget)
    apply_theme(name)
    return name


def accent_soft_for(action: str) -> str:
    """Return the translucent accent wash belonging to *action*.

    Args:
        action: Either ``"unplug"`` or ``"plug_in"``.

    Returns:
        An ``rgba(...)`` string suitable for a style sheet.
    """
    return ACCENT_PLUG_SOFT if action == "plug_in" else ACCENT_UNPLUG_SOFT


def accent_for(action: str) -> str:
    """Return the solid accent colour belonging to *action*.

    Args:
        action: Either ``"unplug"`` or ``"plug_in"``.

    Returns:
        A hex colour string from this token module.
    """
    return ACCENT_PLUG if action == "plug_in" else ACCENT_UNPLUG


def accent_dim_for(action: str) -> str:
    """Return the dimmed accent colour belonging to *action*.

    Used for the unfilled portion of the gauge and for pressed states.
    """
    return ACCENT_PLUG_DIM if action == "plug_in" else ACCENT_UNPLUG_DIM
