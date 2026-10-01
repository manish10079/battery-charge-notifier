"""ViewModel for the system tray status text.

Turns the latest battery sample plus the active configuration into the tray's
menu caption, tooltip and icon. Keeping this out of the tray widget means the
widget never inspects battery state or thresholds.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from ..app_config import AppConfig
from ..battery_service import BatteryState
from ..resources import TRAY_OK, TRAY_PAUSED, TRAY_PLUG, TRAY_UNPLUG

_SECONDS_PER_MINUTE = 60
_SECONDS_PER_HOUR = 3600


def format_duration(seconds: int | None) -> str:
    """Format a duration for the tooltip.

    Args:
        seconds: Duration in seconds, or ``None`` when unknown.

    Returns:
        A compact string such as ``"1 h 32 min"``, or an empty string when the
        duration is unknown.
    """
    if seconds is None or seconds <= 0:
        return ""
    if seconds >= _SECONDS_PER_HOUR:
        hours, remainder = divmod(seconds, _SECONDS_PER_HOUR)
        minutes = remainder // _SECONDS_PER_MINUTE
        return f"{hours} h {minutes} min"
    return f"{max(1, seconds // _SECONDS_PER_MINUTE)} min"


class StatusViewModel(QObject):
    """Derives the tray caption, tooltip and icon from battery + config."""

    #: Emitted whenever any of the derived values changes.
    statusChanged = Signal()

    def __init__(
        self,
        config: AppConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create the ViewModel.

        Args:
            config: Initial configuration.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._config = config or AppConfig()
        self._state: BatteryState | None = None

    # -- updates -----------------------------------------------------------
    def apply_config(self, config: AppConfig) -> None:
        """Adopt a new configuration.

        Args:
            config: The newly committed configuration.
        """
        self._config = config
        self.statusChanged.emit()

    def update_battery(self, state: BatteryState) -> None:
        """Adopt the latest battery sample.

        Args:
            state: The most recent reading.
        """
        self._state = state
        self.statusChanged.emit()

    # -- derived values ----------------------------------------------------
    @property
    def monitoring_enabled(self) -> bool:
        """Whether monitoring is currently enabled."""
        return self._config.monitoring_enabled

    @property
    def has_battery(self) -> bool:
        """Whether the last sample reported a battery."""
        return self._state is not None and self._state.present

    @property
    def action(self) -> str | None:
        """The action the user should take right now, if any.

        Returns:
            ``"unplug"`` when the battery is at or above the upper limit while
            plugged in, ``"plug_in"`` when it is at or below the lower limit on
            battery power, otherwise ``None``.
        """
        if not self.has_battery or not self.monitoring_enabled:
            return None
        assert self._state is not None  # narrowed by has_battery
        if self._state.plugged and self._state.percent >= self._config.upper_limit:
            return "unplug"
        if self._state.on_battery_power and self._state.percent <= self._config.lower_limit:
            return "plug_in"
        return None

    @property
    def caption(self) -> str:
        """The tray menu's status line."""
        if not self.monitoring_enabled:
            return "Status  ·  paused"
        if not self.has_battery:
            return "Status  ·  no battery"
        assert self._state is not None
        if self.action == "unplug":
            return f"Status  ·  {self._state.percent}%  ·  unplug"
        if self.action == "plug_in":
            return f"Status  ·  {self._state.percent}%  ·  plug in"
        return f"Status  ·  {self._state.percent}%"

    @property
    def power_source(self) -> str:
        """A short phrase describing where power is coming from."""
        if not self.has_battery:
            return "No battery detected"
        assert self._state is not None
        return "Charger connected" if self._state.plugged else "Running on battery"

    @property
    def tooltip(self) -> str:
        """Multi-line tooltip for the tray icon."""
        lines = ["Battery Charge Notifier"]
        if not self.has_battery:
            lines.append("No battery detected on this machine.")
        else:
            assert self._state is not None
            lines.append(f"{self._state.percent}%  ·  {self.power_source}")
            estimate = format_duration(self._state.seconds_left)
            if estimate:
                suffix = "to full" if self._state.plugged else "remaining"
                lines.append(f"About {estimate} {suffix}")
        lines.append(
            f"Limits: unplug at {self._config.upper_limit}%, "
            f"plug in at {self._config.lower_limit}%"
        )
        if self.monitoring_enabled:
            lines.append(f"Polling every {self._config.poll_interval_seconds} s")
        else:
            lines.append("Monitoring paused")
        return "\n".join(lines)

    @property
    def icon_name(self) -> str:
        """Bundled asset name for the tray icon."""
        if not self.monitoring_enabled or not self.has_battery:
            return TRAY_PAUSED
        if self.action == "unplug":
            return TRAY_UNPLUG
        if self.action == "plug_in":
            return TRAY_PLUG
        return TRAY_OK


__all__ = ["StatusViewModel", "format_duration"]
