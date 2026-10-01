"""ViewModel for the warning popup.

Converts a :class:`~batterylimit.monitor.WarningEvent` into display-ready text
and exposes the three user actions (snooze, settings, dismiss) as signals. The
window itself contains no formatting or decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import QObject, Signal

from ..app_config import AppConfig
from ..monitor import WarningEvent, WarningKind
from ..resources import action_icon_name


@dataclass(frozen=True)
class WarningContent:
    """Everything the warning window needs to render itself.

    Attributes:
        headline: The required action, shown as the main line of text.
        detail: Full sentence describing the battery level and the action.
        percent: Charge level, 0-100, for the large readout.
        action: ``"unplug"`` or ``"plug_in"``; drives the accent colour.
        icon_name: Bundled asset to show beside the headline.
        snooze_label: Caption for the snooze button, including its duration.
        is_upper: Whether this is the "battery is high" warning.
    """

    headline: str
    detail: str
    percent: int
    action: str
    icon_name: str
    snooze_label: str
    is_upper: bool


class WarningViewModel(QObject):
    """Presents one warning and relays the user's response.

    The same instance is reused for every warning so that the window can be
    updated in place instead of stacking duplicates.
    """

    #: Emitted with a fresh :class:`WarningContent` whenever a warning arrives.
    contentChanged = Signal(object)
    #: Emitted when the user asks to be reminded later.
    snoozeRequested = Signal(object)
    #: Emitted when the user opens the settings dialog from the popup.
    settingsRequested = Signal()
    #: Emitted when the user dismisses the popup.
    dismissed = Signal()

    def __init__(self, config: AppConfig | None = None, parent: QObject | None = None) -> None:
        """Create the ViewModel.

        Args:
            config: Configuration used for the snooze caption.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._config = config or AppConfig()
        self._event: WarningEvent | None = None

    # -- state -------------------------------------------------------------
    @property
    def event(self) -> WarningEvent | None:
        """The warning currently being presented, if any."""
        return self._event

    @property
    def kind(self) -> WarningKind | None:
        """Kind of the warning currently being presented, if any."""
        return self._event.kind if self._event is not None else None

    @property
    def content(self) -> WarningContent | None:
        """Display-ready content, or ``None`` before the first warning."""
        if self._event is None:
            return None
        return self._build_content(self._event)

    @property
    def upper_limit(self) -> int:
        """The configured upper limit, for the gauge's threshold markers."""
        return self._config.upper_limit

    @property
    def lower_limit(self) -> int:
        """The configured lower limit, for the gauge's threshold markers."""
        return self._config.lower_limit

    def apply_config(self, config: AppConfig) -> None:
        """Adopt a new configuration and refresh the visible content.

        Args:
            config: The newly committed configuration.
        """
        self._config = config
        if self._event is not None:
            self.contentChanged.emit(self._build_content(self._event))

    # -- actions -----------------------------------------------------------
    def show(self, event: WarningEvent) -> WarningContent:
        """Present *event*, replacing any warning already on screen.

        Args:
            event: The warning to display.

        Returns:
            The content that was emitted to the view.
        """
        self._event = event
        content = self._build_content(event)
        self.contentChanged.emit(content)
        return content

    def snooze(self) -> None:
        """Report that the user wants to be reminded later."""
        if self._event is not None:
            self.snoozeRequested.emit(self._event.kind)

    def open_settings(self) -> None:
        """Report that the user wants the settings dialog."""
        self.settingsRequested.emit()

    def dismiss(self) -> None:
        """Report that the user dismissed the popup."""
        self.dismissed.emit()

    # -- internals ---------------------------------------------------------
    def _build_content(self, event: WarningEvent) -> WarningContent:
        """Format *event* for display."""
        is_upper = event.kind is WarningKind.UPPER
        minutes = self._config.snooze_minutes
        return WarningContent(
            headline=event.title,
            detail=event.message,
            percent=event.percent,
            action=event.action,
            icon_name=action_icon_name(event.action),
            snooze_label=f"Snooze {minutes} min",
            is_upper=is_upper,
        )


__all__ = ["WarningContent", "WarningViewModel"]
