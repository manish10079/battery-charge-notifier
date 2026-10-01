"""Battery status reading, isolated behind a narrow service seam.

The rest of the application never talks to the operating system directly: it
depends on the :class:`BatteryService` protocol and receives immutable
:class:`BatteryState` values. That keeps the monitoring state machine pure and
lets the test suite drive it with synthetic states.

This module **only reads** battery status. It never writes to battery
firmware, drivers or charging hardware, and it never requests elevated
privileges.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import psutil

logger = logging.getLogger(__name__)

#: Sentinel used by psutil (``POWER_TIME_UNKNOWN``/``POWER_TIME_UNLIMITED``)
#: and by the Windows power API to mean "no meaningful estimate".
UNKNOWN_SECONDS_LEFT = -1

#: Charge level at or above which a plugged-in battery is considered full and
#: therefore no longer charging.
FULL_PERCENT = 100


@dataclass(frozen=True)
class BatteryState:
    """An immutable snapshot of the battery.

    Attributes:
        percent: Charge level, 0-100.
        plugged: Whether external power is connected (AC line status).
        charging: Whether power is currently flowing into the battery. See
            :meth:`PsutilBatteryService.read` for how this is derived.
        seconds_left: Estimated seconds until empty or until full, when the
            platform can provide one; ``None`` otherwise.
        present: ``False`` for the "no battery" sentinel returned on machines
            without a battery (desktops), which suppresses all warnings.
    """

    percent: int
    plugged: bool
    charging: bool
    seconds_left: int | None = None
    present: bool = True

    @classmethod
    def absent(cls) -> BatteryState:
        """Return the sentinel used when no battery can be found."""
        return cls(percent=0, plugged=False, charging=False, seconds_left=None, present=False)

    @property
    def on_battery_power(self) -> bool:
        """Whether the machine is currently running from battery power."""
        return self.present and not self.plugged


@runtime_checkable
class BatteryService(Protocol):
    """Reads the current battery state.

    Implementations must be cheap and non-blocking; they are called from a
    background thread on every poll tick.
    """

    def read(self) -> BatteryState:
        """Return the current battery state.

        Returns:
            The latest snapshot, or :meth:`BatteryState.absent` when the machine
            has no battery or the value cannot be read.
        """
        ...


class PsutilBatteryService:
    """Default :class:`BatteryService`, backed by :mod:`psutil`.

    ``psutil.sensors_battery()`` is the only portable single call that returns
    charge level, AC line status and a time estimate across Windows, macOS and
    Linux, so it is preferred over hand-rolled ``ctypes``/sysfs backends: one
    code path, one runtime dependency, no platform-specific maintenance.
    """

    def read(self) -> BatteryState:
        """Read the battery via ``psutil.sensors_battery()``.

        ``psutil`` does not expose a charging flag on every platform, so
        ``charging`` is derived as "plugged in and not already full". The upper
        warning deliberately keys off ``plugged`` rather than ``charging``, so
        this approximation never changes whether a warning is actionable.

        Returns:
            The current battery state, or :meth:`BatteryState.absent` if the
            snapshot is unavailable or the underlying call fails.
        """
        try:
            snapshot = psutil.sensors_battery()
        except Exception:  # noqa: BLE001 - psutil raises platform-specific errors
            logger.warning("Reading the battery failed", exc_info=True)
            return BatteryState.absent()

        if snapshot is None:
            return BatteryState.absent()

        try:
            percent = max(0, min(FULL_PERCENT, int(snapshot.percent)))
        except (TypeError, ValueError):
            logger.warning("Battery reported an unreadable charge level: %r", snapshot.percent)
            return BatteryState.absent()

        plugged = bool(getattr(snapshot, "power_plugged", False))
        raw_seconds = getattr(snapshot, "secsleft", UNKNOWN_SECONDS_LEFT)
        if raw_seconds is None or not isinstance(raw_seconds, (int, float)):
            seconds_left = None
        elif raw_seconds <= UNKNOWN_SECONDS_LEFT:
            seconds_left = None
        else:
            seconds_left = int(raw_seconds)

        return BatteryState(
            percent=percent,
            plugged=plugged,
            charging=plugged and percent < FULL_PERCENT,
            seconds_left=seconds_left,
            present=True,
        )


__all__ = [
    "BatteryService",
    "BatteryState",
    "PsutilBatteryService",
    "UNKNOWN_SECONDS_LEFT",
]
