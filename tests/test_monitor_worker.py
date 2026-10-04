"""Tests for the polling worker and the threaded monitor facade."""

from __future__ import annotations

import pytest

from battery_charge_notifier.app_config import AppConfig
from battery_charge_notifier.battery_service import BatteryState
from battery_charge_notifier.monitor import BatteryMonitor, BatteryPollWorker, WarningKind

from conftest import StubBatteryService


def make_state(percent: int, plugged: bool, present: bool = True) -> BatteryState:
    """Build a synthetic battery state."""
    return BatteryState(
        percent=percent,
        plugged=plugged,
        charging=plugged and percent < 100,
        present=present,
    )


#: A low upper limit that still satisfies the cross-field validation rule.
LOW_UPPER_CONFIG = AppConfig(upper_limit=3, lower_limit=1, minimum_gap=1)


@pytest.fixture
def worker_factory():
    """Return a factory that builds a worker with the given service/config."""

    def build(service, config: AppConfig | None = None) -> BatteryPollWorker:
        return BatteryPollWorker(service, config or AppConfig())

    return build


class TestPolling:
    def test_publishes_a_state_on_every_poll(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(42, plugged=False))
        worker = worker_factory(service)
        states: list[BatteryState] = []
        worker.batteryUpdated.connect(states.append)

        for _ in range(3):
            worker.poll_once()

        assert [state.percent for state in states] == [42, 42, 42]
        assert service.calls == 3

    def test_absent_battery_publishes_but_never_warns(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(BatteryState.absent())
        worker = worker_factory(service)
        warnings: list = []
        states: list[BatteryState] = []
        worker.warningRaised.connect(warnings.append)
        worker.batteryUpdated.connect(states.append)

        for _ in range(5):
            worker.poll_once()

        assert len(states) == 5
        assert warnings == []

    def test_monitoring_disabled_publishes_but_never_warns(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(90, plugged=True))
        config = AppConfig(upper_limit=80, lower_limit=20, monitoring_enabled=False)
        worker = worker_factory(service, config)
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        for _ in range(5):
            worker.poll_once()

        assert warnings == []

    def test_start_takes_an_immediate_sample(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(50, plugged=False))
        worker = worker_factory(service)
        states: list[BatteryState] = []
        worker.batteryUpdated.connect(states.append)

        worker.start()
        try:
            assert len(states) == 1
        finally:
            worker.stop()


class TestWarningDelivery:
    def test_low_upper_limit_warns_exactly_once(self, qtbot, worker_factory) -> None:
        """Acceptance criterion: with the upper limit at 3%, exactly one warning."""
        service = StubBatteryService(make_state(85, plugged=True))
        worker = worker_factory(service, LOW_UPPER_CONFIG)
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        for _ in range(50):
            worker.poll_once()

        assert len(warnings) == 1
        event = warnings[0]
        assert event.kind is WarningKind.UPPER
        assert event.percent == 85
        assert event.message == "Battery at 85% \u2014 unplug the charger."

    def test_warning_refires_after_the_scripted_recovery(
        self, qtbot, worker_factory
    ) -> None:
        service = StubBatteryService(
            [
                make_state(4, plugged=True),  # fires
                make_state(4, plugged=True),  # quiet
                make_state(1, plugged=True),  # re-arms (below 3 - 1)
                make_state(4, plugged=True),  # fires again
            ]
        )
        worker = worker_factory(service, LOW_UPPER_CONFIG)
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        for _ in range(4):
            worker.poll_once()

        assert len(warnings) == 2

    def test_lower_warning_when_running_on_battery(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(15, plugged=False))
        worker = worker_factory(service, AppConfig(upper_limit=80, lower_limit=20))
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        for _ in range(10):
            worker.poll_once()

        assert len(warnings) == 1
        assert warnings[0].message == "Battery at 15% \u2014 plug in the charger."


class TestLiveConfig:
    def test_new_thresholds_apply_without_restart(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(50, plugged=True))
        worker = worker_factory(service, AppConfig(upper_limit=80, lower_limit=20))
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        worker.poll_once()
        assert warnings == []

        worker.apply_config(AppConfig(upper_limit=40, lower_limit=20))
        worker.poll_once()
        assert len(warnings) == 1

    def test_poll_interval_is_applied_to_the_timer(self, qtbot, worker_factory) -> None:
        worker = worker_factory(StubBatteryService(make_state(50, plugged=False)))
        assert worker.config.poll_interval_ms == 60_000

        worker.apply_config(AppConfig(poll_interval_seconds=30))
        assert worker.timer_interval_ms == 30_000

    def test_disabling_monitoring_stops_the_timer(self, qtbot, worker_factory) -> None:
        worker = worker_factory(StubBatteryService(make_state(50, plugged=False)))
        worker.start()
        assert worker.is_running

        worker.apply_config(AppConfig(monitoring_enabled=False))
        assert not worker.is_running

        worker.apply_config(AppConfig(monitoring_enabled=True))
        assert worker.is_running
        worker.stop()

    def test_snooze_slot_mutes_the_channel(self, qtbot, worker_factory) -> None:
        service = StubBatteryService(make_state(85, plugged=True))
        worker = worker_factory(service, AppConfig(upper_limit=80, lower_limit=20))
        warnings: list = []
        worker.warningRaised.connect(warnings.append)

        worker.poll_once()
        assert len(warnings) == 1

        worker.snooze(WarningKind.UPPER)
        for _ in range(10):
            worker.poll_once()
        assert len(warnings) == 1


class TestThreadedFacade:
    def test_monitor_polls_off_the_ui_thread(self, qtbot) -> None:
        service = StubBatteryService(make_state(66, plugged=False))
        monitor = BatteryMonitor(service, AppConfig(poll_interval_seconds=5))
        try:
            with qtbot.waitSignal(monitor.batteryUpdated, timeout=5000):
                monitor.start()
            assert monitor.latest_state is not None
            assert monitor.latest_state.percent == 66
        finally:
            monitor.stop()
        assert not monitor.is_running

    def test_monitor_raises_warnings_from_the_worker_thread(self, qtbot) -> None:
        service = StubBatteryService(make_state(95, plugged=True))
        monitor = BatteryMonitor(service, LOW_UPPER_CONFIG)
        try:
            with qtbot.waitSignal(monitor.warningRaised, timeout=5000) as blocker:
                monitor.start()
            assert blocker.args[0].percent == 95
        finally:
            monitor.stop()

    def test_monitor_applies_config_changes(self, qtbot) -> None:
        service = StubBatteryService(make_state(50, plugged=True))
        monitor = BatteryMonitor(service, AppConfig(poll_interval_seconds=5))
        try:
            monitor.apply_config(AppConfig(poll_interval_seconds=30))
            assert monitor.config.poll_interval_seconds == 30
        finally:
            monitor.stop()
