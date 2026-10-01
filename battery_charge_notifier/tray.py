"""The system tray icon - the application's primary home.

The tray exposes the live status line, the settings dialog, a pause switch, a
way to preview the warnings and a quit action. Like every other View it holds no
business logic: the caption, tooltip and icon are computed by
:class:`~battery_charge_notifier.viewmodels.status.StatusViewModel`, and every command is
reported as a signal for the controller to act on.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from . import resources
from .viewmodels.status import StatusViewModel

logger = logging.getLogger(__name__)


class TrayIcon(QObject):
    """A ``QSystemTrayIcon`` with Battery Charge Notifier's menu."""

    #: Emitted when the user opens the settings dialog.
    settingsRequested = Signal()
    #: Emitted with ``"upper"`` or ``"lower"`` when the user previews a warning.
    testWarningRequested = Signal(str)
    #: Emitted when the user flips the pause switch, with the requested state.
    monitoringToggleRequested = Signal(bool)
    #: Emitted when the user quits.
    quitRequested = Signal()

    def __init__(
        self,
        viewmodel: StatusViewModel,
        parent: QObject | None = None,
    ) -> None:
        """Create the tray icon and its menu.

        Args:
            viewmodel: Supplies the status caption, tooltip and icon.
            parent: Optional Qt parent (typically the ``QApplication``).
        """
        super().__init__(parent)
        self._viewmodel = viewmodel

        self._icon = QSystemTrayIcon(parent)
        self._icon.setIcon(resources.load_icon(resources.TRAY_OK))
        self._icon.setContextMenu(self._build_menu())
        self._icon.activated.connect(self._on_activated)

        viewmodel.statusChanged.connect(self.refresh)

    # -- API ---------------------------------------------------------------
    @property
    def is_available(self) -> bool:
        """Whether the desktop environment provides a system tray."""
        return QSystemTrayIcon.isSystemTrayAvailable()

    @property
    def icon(self) -> QSystemTrayIcon:
        """The underlying ``QSystemTrayIcon``, used for balloon messages."""
        return self._icon

    @property
    def status_text(self) -> str:
        """The read-only status line shown at the top of the menu."""
        return self._status_action.text()

    @property
    def tooltip_text(self) -> str:
        """The tray icon's tooltip."""
        return self._icon.toolTip()

    @property
    def is_paused(self) -> bool:
        """Whether the pause switch is currently engaged."""
        return self._toggle_action.isChecked()

    def show(self) -> None:
        """Show the tray icon. Has no effect where no tray is available."""
        self.refresh()
        self._icon.show()

    def hide(self) -> None:
        """Hide the tray icon."""
        self._icon.hide()

    def refresh(self) -> None:
        """Re-read the caption, tooltip and icon from the ViewModel."""
        self._status_action.setText(self._viewmodel.caption)
        self._toggle_action.setChecked(not self._viewmodel.monitoring_enabled)
        self._toggle_action.setText(
            "Resume monitoring" if not self._viewmodel.monitoring_enabled else "Pause monitoring"
        )

        icon = resources.load_icon(self._viewmodel.icon_name)
        if not icon.isNull():
            self._icon.setIcon(icon)

        self._icon.setToolTip(self._viewmodel.tooltip)

    # -- construction ------------------------------------------------------
    def _build_menu(self) -> QMenu:
        """Create the context menu."""
        menu = QMenu()

        self._status_action = menu.addAction(self._viewmodel.caption)
        self._status_action.setEnabled(False)

        menu.addSeparator()

        settings = menu.addAction("Settings\u2026")
        settings.triggered.connect(self.settingsRequested)

        test_menu = menu.addMenu("Test warnings")
        upper = test_menu.addAction("Upper warning (unplug)")
        upper.triggered.connect(lambda: self.testWarningRequested.emit("upper"))
        lower = test_menu.addAction("Lower warning (plug in)")
        lower.triggered.connect(lambda: self.testWarningRequested.emit("lower"))

        menu.addSeparator()

        self._toggle_action = menu.addAction("Pause monitoring")
        self._toggle_action.setCheckable(True)
        self._toggle_action.toggled.connect(self._on_toggle)

        menu.addSeparator()

        quit_action = menu.addAction("Quit Battery Charge Notifier")
        quit_action.triggered.connect(self.quitRequested)

        return menu

    # -- events ------------------------------------------------------------
    def _on_toggle(self, paused: bool) -> None:
        """Translate the checkable action into "should monitoring be enabled"."""
        self.monitoringToggleRequested.emit(not paused)

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Open settings on double-click, which is the conventional gesture."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.settingsRequested.emit()


__all__ = ["TrayIcon"]
