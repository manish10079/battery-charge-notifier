"""Reusable, presentation-only widgets.

Widgets in this package render whatever they are given and report user intent
through signals; they deliberately contain no business logic.
"""

from __future__ import annotations

from .action_button import ActionButton, ButtonRole
from .battery_gauge import BatteryGauge

__all__ = ["ActionButton", "BatteryGauge", "ButtonRole"]
