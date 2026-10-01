"""Design tokens for Battery Charge Notifier.

This module is the **only** place in the codebase where a colour literal may
appear. Every widget, style sheet and generated icon pulls its colours from
the named tokens below, so the whole application can be re-themed by editing
this single file.

The palette is a dark, Material-3-flavoured scheme: deep desaturated blue-grey
surfaces, generous tonal steps for elevation, and two semantic accents - amber
for "stop charging" and coral for "charge now".
"""

from __future__ import annotations

# --------------------------------------------------------------------------
# Surfaces (darkest -> lightest, i.e. lowest -> highest elevation)
# --------------------------------------------------------------------------
SURFACE: str = "#0E1317"
SURFACE_CONTAINER_LOW: str = "#141B21"
SURFACE_CONTAINER: str = "#1A232A"
SURFACE_CONTAINER_HIGH: str = "#222D36"
SURFACE_OVERLAY: str = "#2A3742"

# A near-opaque scrim used behind the frameless popup so the desktop shows
# through faintly (the window is translucent).
SCRIM: str = "rgba(14, 19, 23, 242)"
SCRIM_SOFT: str = "rgba(20, 27, 33, 224)"

# --------------------------------------------------------------------------
# Lines
# --------------------------------------------------------------------------
OUTLINE: str = "#2E3A44"
OUTLINE_STRONG: str = "#3C4B57"

# --------------------------------------------------------------------------
# Text
# --------------------------------------------------------------------------
TEXT_PRIMARY: str = "#E9EFF4"
TEXT_SECONDARY: str = "#9DAEBB"
TEXT_MUTED: str = "#6C7C89"
TEXT_ON_ACCENT: str = "#0B1116"

# --------------------------------------------------------------------------
# Semantic accents
# --------------------------------------------------------------------------
# Battery is high while plugged in: the action is to *stop* charging.
ACCENT_UNPLUG: str = "#F4B04A"
ACCENT_UNPLUG_DIM: str = "#8A6528"
ACCENT_UNPLUG_SOFT: str = "rgba(244, 176, 74, 38)"

# Battery is low on battery power: the action is to *start* charging.
ACCENT_PLUG: str = "#FF6B6B"
ACCENT_PLUG_DIM: str = "#8C3A3A"
ACCENT_PLUG_SOFT: str = "rgba(255, 107, 107, 38)"

# Neutral / informational accent used by primary buttons and the gauge track.
ACCENT_PRIMARY: str = "#5AA9E6"
ACCENT_PRIMARY_DIM: str = "#356487"
ACCENT_PRIMARY_SOFT: str = "rgba(90, 169, 230, 38)"

# Tray icon glyph + healthy state.
ACCENT_OK: str = "#4FD1A5"

# --------------------------------------------------------------------------
# Component tokens
# --------------------------------------------------------------------------
GAUGE_TRACK: str = "#202B34"
GAUGE_TICK: str = "#3A4854"
GAUGE_TICK_MAJOR: str = "#5B6D7C"

BUTTON_BACKGROUND: str = "#212C35"
BUTTON_BACKGROUND_HOVER: str = "#2C3A45"
BUTTON_BACKGROUND_PRESSED: str = "#18212A"
BUTTON_TEXT: str = "#DCE6ED"

INPUT_BACKGROUND: str = "#141B21"
INPUT_BORDER: str = "#33414C"
INPUT_BORDER_FOCUS: str = ACCENT_PRIMARY
INPUT_INVALID_BORDER: str = ACCENT_PLUG

FIELD_LABEL: str = "#C3D0DA"
FIELD_HELP: str = "#7E8E9B"
FIELD_ERROR: str = "#FF8A8A"

SCROLLBAR_HANDLE: str = "#39485488"
SCROLLBAR_HANDLE_HOVER: str = "#4A5B69"

# Colour used for the opaque parts of the generated app/tray icons.
ICON_BACKGROUND: str = "#101820"
ICON_FOREGROUND: str = "#E9EFF4"

#: Pass-through keyword for style sheets that must not paint a background.
TRANSPARENT: str = "transparent"


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
