"""Warning dispatch to the popup window and to tray notifications.

The notifier owns exactly one :class:`~battery_charge_notifier.warning_window.WarningWindow`,
so a second warning updates the window that is already on screen instead of
stacking duplicates. :attr:`~battery_charge_notifier.app_config.AppConfig.notification_mode`
chooses *either* the popup *or* a tray balloon, never both.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from .app_config import AppConfig
from .battery_service import BatteryState
from .monitor import WarningEvent, WarningKind
from .viewmodels.warning import WarningContent, WarningViewModel
from .warning_window import WarningWindow

logger = logging.getLogger(__name__)

BALLOON_TIMEOUT_MS = 12_000


class Notifier(QObject):
    """Turns :class:`WarningEvent` values into things the user can see."""

    #: Emitted when the user asks for settings from the popup.
    settingsRequested = Signal()
    #: Emitted with a :class:`WarningKind` when the user snoozes.
    snoozeRequested = Signal(object)
    #: Emitted when the popup is dismissed.
    dismissed = Signal()

    def __init__(
        self,
        config: AppConfig | None = None,
        tray_icon: QSystemTrayIcon | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create the notifier.

        Args:
            config: Initial configuration; decides popup-vs-tray.
            tray_icon: Tray icon used for balloon messages, if the platform has one.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._config = config or AppConfig()
        self._tray_icon = tray_icon
        self._window: WarningWindow | None = None
        self._auto_close = QTimer(self)
        self._auto_close.setSingleShot(True)
        self._auto_close.timeout.connect(self._on_popup_timeout)

        self._viewmodel = WarningViewModel(self._config, self)
        self._viewmodel.snoozeRequested.connect(self._on_snooze)
        self._viewmodel.settingsRequested.connect(self.settingsRequested)
        self._viewmodel.dismissed.connect(self._on_dismissed)

    # -- accessors ---------------------------------------------------------
    @property
    def viewmodel(self) -> WarningViewModel:
        """The ViewModel behind the popup."""
        return self._viewmodel

    @property
    def window(self) -> WarningWindow | None:
        """The popup window, once it has been created."""
        return self._window

    def is_popup_visible(self) -> bool:
        """Whether the warning popup is currently on screen."""
        return self._window is not None and self._window.isVisible()

    # -- configuration -----------------------------------------------------
    def apply_config(self, config: AppConfig) -> None:
        """Adopt a new configuration.

        Args:
            config: The newly committed configuration.
        """
        self._config = config
        self._viewmodel.apply_config(config)
        if self.is_popup_visible():
            self._arm_popup_timeout()

    def restyle(self) -> None:
        """Repaint an open popup after the theme tokens change."""
        if self._window is None or self._viewmodel.content is None:
            return
        self._window.apply_content(self._viewmodel.content)
        from .widgets import ActionButton

        for button in self._window.findChildren(ActionButton):
            button.set_role(button.role)
            button.set_action(getattr(button, "_action", "unplug"))

    def set_tray_icon(self, tray_icon: QSystemTrayIcon | None) -> None:
        """Attach (or detach) the tray icon used for balloon messages."""
        self._tray_icon = tray_icon

    # -- behaviour ---------------------------------------------------------
    def notify(self, event: WarningEvent) -> None:
        """Present *event* to the user.

        Args:
            event: The warning to present.
        """
        content = self._viewmodel.show(event)
        self._present(content)

    def present_test_warning(self, kind: WarningKind, percent: int) -> None:
        """Preview a warning using the same channel as a real one.

        Args:
            kind: Which warning to demonstrate.
            percent: Charge level to show in the message.
        """
        content = self._viewmodel.show(
            WarningEvent(kind=kind, percent=percent, fired_at=time.monotonic())
        )
        self._present(content)

    def _present(self, content: WarningContent) -> None:
        """Show *content* on the channel selected in settings."""
        if self._config.notification_mode == "popup":
            logger.info("Showing popup: %s", content.headline)
            self._present_popup()
            return
        if self._show_balloon(content):
            logger.info("Showing tray notification: %s", content.headline)
            return
        logger.warning(
            "Tray notifications are unavailable on this session; showing the popup instead"
        )
        self._present_popup()

    def observe_battery(self, state: BatteryState) -> None:
        """Hide the warning once the user takes the requested charger action.

        A plug-in warning closes itself when AC is connected. An unplug warning
        closes itself when the charger is removed. If the charger state does
        not change, the popup stays until the user dismisses it.

        Args:
            state: The latest battery sample.
        """
        if not self.is_popup_visible():
            return
        content = self._viewmodel.content
        if content is None:
            return
        if content.action == "plug_in" and state.plugged:
            logger.info("Charger plugged in; auto-dismissing plug-in warning")
            self.dismiss()
            return
        if content.action == "unplug" and not state.plugged:
            logger.info("Charger unplugged; auto-dismissing unplug warning")
            self.dismiss()

    def dismiss(self) -> None:
        """Slide the popup out, then hide it."""
        self._auto_close.stop()
        if self._window is not None:
            self._window.slide_out_and_hide()

    # -- internals ---------------------------------------------------------
    def _present_popup(self) -> None:
        """Create the popup on first use, then show it in place."""
        if self._window is None:
            self._window = WarningWindow(self._viewmodel)
            # The ViewModel emitted its content before the window existed, so
            # seed the freshly created window with the current warning.
            current = self._viewmodel.content
            if current is not None:
                self._window.apply_content(current)
        self._window.show_at_bottom_right()
        self._arm_popup_timeout()

    def _arm_popup_timeout(self) -> None:
        """Start or cancel the auto-close timer from the current setting.

        ``popup_timeout_seconds`` of 0 means no timeout.
        """
        self._auto_close.stop()
        seconds = self._config.popup_timeout_seconds
        if seconds > 0 and self.is_popup_visible():
            self._auto_close.start(seconds * 1000)

    def _on_popup_timeout(self) -> None:
        """Close the popup when the configured timeout elapses."""
        logger.info("Popup timeout elapsed; dismissing")
        self.dismiss()

    def _show_balloon(self, content: WarningContent) -> bool:
        """Show a tray balloon. Return whether the platform accepted it."""
        if self._tray_icon is None or not QSystemTrayIcon.isSystemTrayAvailable():
            logger.warning("No system tray; cannot show a balloon")
            return False
        if not QSystemTrayIcon.supportsMessages():
            logger.warning("This desktop does not support tray balloons")
            return False
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if content.action == "plug_in"
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray_icon.showMessage(content.headline, content.detail, icon, BALLOON_TIMEOUT_MS)
        return True

    def _on_snooze(self, kind: WarningKind) -> None:
        """Hide the popup and forward the snooze request."""
        self.dismiss()
        self.snoozeRequested.emit(kind)

    def _on_dismissed(self) -> None:
        """Hide the popup when the user dismisses it."""
        self.dismiss()
        self.dismissed.emit()


__all__ = ["Notifier"]
