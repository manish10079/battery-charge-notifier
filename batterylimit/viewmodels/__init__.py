"""ViewModels: the presentation layer between the services and the widgets.

A ViewModel owns all formatting and decision logic so that the widgets in
:mod:`batterylimit.widgets`, :mod:`batterylimit.warning_window` and
:mod:`batterylimit.settings_dialog` stay passive: they render what they are
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
