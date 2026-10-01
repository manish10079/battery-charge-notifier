"""Battery polling and the warning/re-arm state machine.

The module is split into three layers so that the interesting logic is pure and
trivially testable:

``WarningStateMachine``
    A Qt-free, deterministic hysteresis state machine. Given a battery state and
    a monotonic timestamp it returns at most one :class:`WarningEvent`. All
    "should we nag the user?" decisions live here.

``BatteryPollWorker``
    A ``QObject`` that owns the polling ``QTimer`` and the state machine. It is
    designed to be moved to a worker thread, but works perfectly well standalone
    (which is how the tests drive it).

``BatteryMonitor``
    A GUI-thread facade that owns the ``QThread``, relays the worker's signals to
    the UI, and forwards control commands back to the worker through queued
    connections so that the state machine is only ever touched by one thread.

Warnings are *latched*: once a warning fires the corresponding channel stays
quiet until the battery has moved back past its re-arm point. This is what
stops the application from nagging on every poll tick.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from enum import StrEnum

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal, Slot

from .app_config import AppConfig
from .battery_service import BatteryService, BatteryState

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------
class WarningKind(StrEnum):
    """Which of the two thresholds a warning belongs to."""

    UPPER = "upper"
    LOWER = "lower"


class ChannelPhase(StrEnum):
    """Phase of a single threshold's hysteresis channel.

    Attributes:
        ARMED: Ready to fire as soon as the warning is actionable.
        QUIET: A warning has fired; latched until the re-arm point is crossed.
        SNOOZED: The user asked to be left alone; suppressed until the deadline.
    """

    ARMED = "armed"
    QUIET = "quiet"
    SNOOZED = "snoozed"


@dataclass(frozen=True)
class Thresholds:
    """The numeric limits that drive the state machine."""

    upper_limit: int = 80
    lower_limit: int = 20
    rearm_gap: int = 5
    snooze_seconds: int = 900

    @classmethod
    def from_config(cls, config: AppConfig) -> Thresholds:
        """Build thresholds from a persisted :class:`AppConfig`."""
        return cls(
            upper_limit=config.upper_limit,
            lower_limit=config.lower_limit,
            rearm_gap=config.rearm_gap,
            snooze_seconds=config.snooze_seconds,
        )

    @property
    def upper_rearm_point(self) -> int:
        """The charge level the battery must fall *below* to re-arm the upper warning."""
        return self.upper_limit - self.rearm_gap

    @property
    def lower_rearm_point(self) -> int:
        """The charge level the battery must rise *above* to re-arm the lower warning."""
        return self.lower_limit + self.rearm_gap


@dataclass(frozen=True)
class WarningEvent:
    """A single actionable warning the user must be told about."""

    kind: WarningKind
    percent: int
    fired_at: float

    @property
    def action(self) -> str:
        """The action the user must take: ``"unplug"`` or ``"plug_in"``."""
        return "unplug" if self.kind is WarningKind.UPPER else "plug_in"

    @property
    def title(self) -> str:
        """Short headline naming the required action."""
        return "Unplug the charger" if self.kind is WarningKind.UPPER else "Plug in the charger"

    @property
    def message(self) -> str:
        """Full user-facing sentence describing the situation."""
        verb = "unplug" if self.kind is WarningKind.UPPER else "plug in"
        return f"Battery at {self.percent}% \u2014 {verb} the charger."


# ---------------------------------------------------------------------------
# Pure state machine
# ---------------------------------------------------------------------------
@dataclass
class _Channel:
    """Mutable hysteresis state for one threshold."""

    phase: ChannelPhase = ChannelPhase.ARMED
    snooze_until: float | None = None


class WarningStateMachine:
    """Decides when to warn the user, with hysteresis and snooze support.

    The machine owns two independent channels (upper and lower). Each channel
    moves between :class:`ChannelPhase` values as follows::

        ARMED --(actionable)--> QUIET --(re-armed)--> ARMED
        QUIET --(snooze)------> SNOOZED --(expired & actionable)--> QUIET
        SNOOZED --(re-armed)--> ARMED

    The machine is completely deterministic: every method that depends on time
    takes an explicit ``now`` argument.
    """

    def __init__(self, thresholds: Thresholds | None = None) -> None:
        """Create a machine with both channels armed.

        Args:
            thresholds: Initial thresholds. Defaults to :class:`Thresholds`.
        """
        self._thresholds = thresholds or Thresholds()
        self._channels: dict[WarningKind, _Channel] = {
            WarningKind.UPPER: _Channel(),
            WarningKind.LOWER: _Channel(),
        }

    @property
    def thresholds(self) -> Thresholds:
        """The thresholds currently in force."""
        return self._thresholds

    def apply_thresholds(self, thresholds: Thresholds) -> None:
        """Adopt new thresholds.

        The latched phases are deliberately preserved: changing a limit in the
        settings dialog applies live and must not re-fire a warning the user has
        already acknowledged.

        Args:
            thresholds: The new thresholds.
        """
        self._thresholds = thresholds

    def phase(self, kind: WarningKind) -> ChannelPhase:
        """Return the current phase of *kind*."""
        return self._channels[kind].phase

    def is_snoozed(self, kind: WarningKind, now: float) -> bool:
        """Return whether *kind* is still muted by an active snooze."""
        channel = self._channels[kind]
        return channel.phase is ChannelPhase.SNOOZED and (
            channel.snooze_until is None or now < channel.snooze_until
        )

    def snooze(self, kind: WarningKind, now: float | None = None) -> None:
        """Mute *kind* for the configured snooze duration.

        Args:
            kind: The channel to mute.
            now: Monotonic timestamp; defaults to the current clock.
        """
        moment = time.monotonic() if now is None else now
        channel = self._channels[kind]
        channel.phase = ChannelPhase.SNOOZED
        channel.snooze_until = moment + self._thresholds.snooze_seconds

    def snooze_all(self, now: float | None = None) -> None:
        """Mute both channels."""
        self.snooze(WarningKind.UPPER, now)
        self.snooze(WarningKind.LOWER, now)

    def reset(self) -> None:
        """Re-arm both channels and clear any snooze."""
        for channel in self._channels.values():
            channel.phase = ChannelPhase.ARMED
            channel.snooze_until = None

    def update(self, state: BatteryState, now: float | None = None) -> WarningEvent | None:
        """Advance the machine by one observation.

        Args:
            state: The battery sample to evaluate.
            now: Monotonic timestamp; defaults to the current clock.

        Returns:
            The warning to raise, or ``None`` when the user should be left alone.
        """
        if not state.present:
            return None

        moment = time.monotonic() if now is None else now
        limits = self._thresholds

        # Both channels are stepped on every observation so that neither can be
        # skipped; the upper channel is reported first, though the two are
        # mutually exclusive by construction (one needs the charger plugged in,
        # the other needs it unplugged).
        upper = self._step(
            kind=WarningKind.UPPER,
            now=moment,
            actionable=state.plugged and state.percent >= limits.upper_limit,
            rearmed=state.percent < limits.upper_rearm_point,
            percent=state.percent,
        )
        lower = self._step(
            kind=WarningKind.LOWER,
            now=moment,
            actionable=(not state.plugged) and state.percent <= limits.lower_limit,
            rearmed=state.percent > limits.lower_rearm_point,
            percent=state.percent,
        )
        return upper or lower

    def _step(
        self,
        *,
        kind: WarningKind,
        now: float,
        actionable: bool,
        rearmed: bool,
        percent: int,
    ) -> WarningEvent | None:
        """Advance a single channel and return its warning, if any."""
        channel = self._channels[kind]

        if channel.phase is ChannelPhase.SNOOZED:
            if channel.snooze_until is not None and now < channel.snooze_until:
                # Muted. Nothing else happens until the deadline, when the
                # decision below re-evaluates the situation from scratch.
                return None
            # Snooze elapsed: this is a "remind me later", so re-arm and
            # re-evaluate. If the battery has recovered in the meantime the
            # `actionable` test fails and the user is left alone.
            channel.snooze_until = None
            channel.phase = ChannelPhase.ARMED

        if channel.phase is ChannelPhase.QUIET:
            if rearmed:
                channel.phase = ChannelPhase.ARMED
            return None

        if not actionable:
            return None

        channel.phase = ChannelPhase.QUIET
        return WarningEvent(kind=kind, percent=percent, fired_at=now)


# ---------------------------------------------------------------------------
# Worker
# ---------------------------------------------------------------------------
class BatteryPollWorker(QObject):
    """Polls the battery on a timer and drives the state machine.

    This object is thread-affine: it must only be used from the thread it lives
    in. :class:`BatteryMonitor` handles that for the application, and the tests
    use it directly on the main thread.
    """

    #: Emitted with a :class:`BatteryState` on every successful poll.
    batteryUpdated = Signal(object)
    #: Emitted with a :class:`WarningEvent` when the user must be warned.
    warningRaised = Signal(object)

    def __init__(
        self,
        service: BatteryService,
        config: AppConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create the worker.

        Args:
            service: Injected battery reader.
            config: Initial configuration. Defaults to :class:`AppConfig`.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._service = service
        self._config = config or AppConfig()
        self._machine = WarningStateMachine(Thresholds.from_config(self._config))

        self._timer = QTimer(self)
        self._timer.setTimerType(Qt.TimerType.VeryCoarseTimer)
        self._timer.setInterval(self._config.poll_interval_ms)
        self._timer.timeout.connect(self.poll_once)

    # -- accessors ---------------------------------------------------------
    @property
    def config(self) -> AppConfig:
        """The configuration currently in force."""
        return self._config

    @property
    def machine(self) -> WarningStateMachine:
        """The state machine, exposed for inspection and tests."""
        return self._machine

    @property
    def is_running(self) -> bool:
        """Whether the polling timer is active."""
        return self._timer.isActive()

    @property
    def timer_interval_ms(self) -> int:
        """The interval currently configured on the polling timer."""
        return self._timer.interval()

    # -- control -----------------------------------------------------------
    @Slot()
    def start(self) -> None:
        """Start polling. Takes one immediate sample so the UI is populated."""
        self._timer.start()
        self.poll_once()

    @Slot()
    def stop(self) -> None:
        """Stop polling."""
        self._timer.stop()

    @Slot(object)
    def apply_config(self, config: AppConfig) -> None:
        """Apply a new configuration live.

        Thresholds are re-read on every poll, so only the interval, the enabled
        flag and the cached copy need updating here.

        Args:
            config: The newly committed configuration.
        """
        self._config = config
        self._machine.apply_thresholds(Thresholds.from_config(config))

        if self._config.monitoring_enabled:
            if self._timer.interval() != config.poll_interval_ms:
                self._timer.setInterval(config.poll_interval_ms)
            if not self._timer.isActive():
                self._timer.start()
                self.poll_once()
        else:
            self._timer.stop()

    @Slot(object)
    def snooze(self, kind: WarningKind) -> None:
        """Mute *kind* for the configured snooze duration.

        Args:
            kind: The warning channel to mute.
        """
        self._machine.snooze(kind)

    @Slot()
    def force_poll(self) -> None:
        """Take a sample immediately without changing the timer state."""
        self.poll_once()

    # -- work --------------------------------------------------------------
    @Slot()
    def poll_once(self) -> None:
        """Read the battery, publish it, and raise a warning if warranted.

        This is the only place the service is touched, and it is safe to call
        directly from tests.
        """
        state = self._service.read()
        self.batteryUpdated.emit(state)

        if not state.present or not self._config.monitoring_enabled:
            return

        event = self._machine.update(state)
        if event is not None:
            logger.info(
                "Raising %s warning at %d%% (plugged=%s)",
                event.kind.value,
                event.percent,
                state.plugged,
            )
            self.warningRaised.emit(event)


# ---------------------------------------------------------------------------
# GUI-thread facade
# ---------------------------------------------------------------------------
class BatteryMonitor(QObject):
    """GUI-thread facade that runs :class:`BatteryPollWorker` on its own thread.

    The worker owns the polling timer, so the (potentially blocking) battery
    read never runs on the UI thread. All commands are delivered to the worker
    through queued connections, which keeps the state machine confined to a
    single thread.
    """

    #: Emitted with a :class:`BatteryState` on every poll.
    batteryUpdated = Signal(object)
    #: Emitted with a :class:`WarningEvent` when the user must be warned.
    warningRaised = Signal(object)

    _configRequested = Signal(object)
    _snoozeRequested = Signal(object)
    _stopRequested = Signal()
    _pollRequested = Signal()

    def __init__(
        self,
        service: BatteryService,
        config: AppConfig | None = None,
        parent: QObject | None = None,
    ) -> None:
        """Create the monitor and start its worker thread.

        Args:
            service: Injected battery reader.
            config: Initial configuration.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._config = config or AppConfig()
        self._latest: BatteryState | None = None

        self._thread = QThread()
        self._thread.setObjectName("BatteryLimitMonitor")
        self._worker = BatteryPollWorker(service, self._config)
        self._worker.moveToThread(self._thread)

        self._worker.batteryUpdated.connect(self._on_battery_updated)
        self._worker.warningRaised.connect(self.warningRaised)

        self._configRequested.connect(self._worker.apply_config)
        self._snoozeRequested.connect(self._worker.snooze)
        self._stopRequested.connect(self._worker.stop)
        self._pollRequested.connect(self._worker.force_poll)
        self._thread.started.connect(self._worker.start)

    # -- accessors ---------------------------------------------------------
    @property
    def latest_state(self) -> BatteryState | None:
        """The most recent battery sample, or ``None`` before the first poll."""
        return self._latest

    @property
    def config(self) -> AppConfig:
        """The configuration currently in force."""
        return self._config

    @property
    def is_running(self) -> bool:
        """Whether the worker thread is running."""
        return self._thread.isRunning()

    # -- control -----------------------------------------------------------
    def start(self) -> None:
        """Start the worker thread and begin polling."""
        if not self._thread.isRunning():
            self._thread.start()

    def stop(self) -> None:
        """Stop polling and shut the worker thread down."""
        if not self._thread.isRunning():
            return
        self._stopRequested.emit()
        self._thread.quit()
        if not self._thread.wait(3000):
            logger.warning("Monitor thread did not shut down cleanly")

    def apply_config(self, config: AppConfig) -> None:
        """Push a new configuration to the worker.

        Args:
            config: The newly committed configuration.
        """
        self._config = config
        self._configRequested.emit(config)

    def snooze(self, kind: WarningKind) -> None:
        """Mute *kind* for the configured snooze duration.

        Args:
            kind: The warning channel to mute.
        """
        self._snoozeRequested.emit(kind)

    def force_poll(self) -> None:
        """Ask the worker to take a sample immediately, off the UI thread.

        This is asynchronous: the resulting ``batteryUpdated`` and
        ``warningRaised`` signals are delivered through the event loop.
        """
        self._pollRequested.emit()

    @Slot(object)
    def _on_battery_updated(self, state: BatteryState) -> None:
        """Cache the newest sample and re-broadcast it."""
        self._latest = state
        self.batteryUpdated.emit(state)


__all__ = [
    "BatteryMonitor",
    "BatteryPollWorker",
    "ChannelPhase",
    "Thresholds",
    "WarningEvent",
    "WarningKind",
    "WarningStateMachine",
]
