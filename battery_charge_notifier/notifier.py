"""Warning dispatch to the popup window and to tray notifications.

The notifier owns exactly one :class:`~battery_charge_notifier.warning_window.WarningWindow`,
so a second warning updates the window that is already on screen instead of
stacking duplicates. Every warning is *also* mirrored to a tray balloon when a
tray is available, so the message is not missed if the popup is dismissed or the
user is away from the screen.
"""

from __future__ import annotations

import logging
import time

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QSystemTrayIcon

from .app_config import AppConfig
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

        if self._config.notification_mode == "popup":
            self._present_popup()
        else:
            # Tray-only mode still needs the balloon below.
            logger.debug("Tray-only mode: skipping the popup for %s", event.kind.value)

        self._show_balloon(content)

    def present_test_warning(self, kind: WarningKind, percent: int) -> None:
        """Show the popup for a synthetic warning, ignoring tray-only mode.

        Used by the tray's "Test warnings" action, where the whole point is to
        see what the popup looks like.

        Args:
            kind: Which warning to demonstrate.
            percent: Charge level to show in the message.
        """
        content = self._viewmodel.show(
            WarningEvent(kind=kind, percent=percent, fired_at=time.monotonic())
        )
        self._present_popup()
        self._show_balloon(content)

    def dismiss(self) -> None:
        """Hide the popup if it is open."""
        if self._window is not None:
            self._window.hide()

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

    def _show_balloon(self, content: WarningContent) -> None:
        """Mirror the warning to a tray balloon, when a tray exists."""
        if self._tray_icon is None or not QSystemTrayIcon.isSystemTrayAvailable():
            return
        icon = (
            QSystemTrayIcon.MessageIcon.Critical
            if content.action == "plug_in"
            else QSystemTrayIcon.MessageIcon.Information
        )
        self._tray_icon.showMessage(content.headline, content.detail, icon, BALLOON_TIMEOUT_MS)

    def _on_snooze(self, kind: WarningKind) -> None:
        """Hide the popup and forward the snooze request."""
        self.dismiss()
        self.snoozeRequested.emit(kind)

    def _on_dismissed(self) -> None:
        """Hide the popup when the user dismisses it."""
        self.dismiss()
        self.dismissed.emit()


__all__ = ["Notifier"]
