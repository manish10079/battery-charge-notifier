"""ViewModels: the presentation layer between the services and the widgets.

A ViewModel owns all formatting and decision logic so that the widgets in
:mod:`battery_charge_notifier.widgets`, :mod:`battery_charge_notifier.warning_window` and
:mod:`battery_charge_notifier.settings_dialog` stay passive: they render what they are
given and report user intent back through Qt signals.
"""

from __future__ import annotations

from .settings import SettingsViewModel
from .status import StatusViewModel
from .warning import WarningContent, WarningViewModel

__all__ = [
    "SettingsViewModel",
    "StatusViewModel",
    "WarningContent",
    "WarningViewModel",
]
