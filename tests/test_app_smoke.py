"""End-to-end smoke tests: the whole application, driven by synthetic batteries.

These build the real object graph - monitor thread, tray, notifier, ViewModels -
with a stubbed :class:`BatteryService`, a temporary configuration file and a
no-op autostart service, so nothing on the host machine is touched.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from PySide6.QtWidgets import QLabel

from battery_charge_notifier.app_config import AppConfig, ConfigManager
from battery_charge_notifier.controller import AppController
from battery_charge_notifier.monitor import WarningKind
from battery_charge_notifier.startup import NoopStartupService

from conftest import StubBatteryService


def make_state(percent: int, plugged: bool):
    """Build a synthetic battery state."""
    from battery_charge_notifier.battery_service import BatteryState

    return BatteryState(
        percent=percent,
        plugged=plugged,
        charging=plugged and percent < 100,
        present=True,
    )


@pytest.fixture
def build_app(qapp, tmp_path: Path):
    """Factory that assembles a fully wired controller with test doubles."""
    controllers: list[AppController] = []

    def build(states, **config_overrides) -> tuple[AppController, ConfigManager, StubBatteryService]:
        settings = {"poll_interval_seconds": 5, **config_overrides}
        manager = ConfigManager(tmp_path / "config.json")
        manager.save(AppConfig(**settings))

        service = StubBatteryService(states)
        controller = AppController(
            qapp,
            battery_service=service,
            config_manager=manager,
            startup_service=NoopStartupService(),
            sync_startup=False,
        )
        controllers.append(controller)
        return controller, manager, service

    yield build

    for controller in controllers:
        controller.shutdown()


class TestBoot:
    def test_app_boots_with_a_stubbed_battery_service(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(make_state(55, plugged=False))

        with qtbot.waitSignal(controller.monitor.batteryUpdated, timeout=5000):
            controller.start()

        assert controller.monitor.latest_state is not None
        assert controller.monitor.latest_state.percent == 55
        assert "55%" in controller.status_viewmodel.caption

    def test_boots_on_a_machine_without_a_battery(self, qtbot, build_app) -> None:
        from battery_charge_notifier.battery_service import BatteryState

        controller, _manager, _service = build_app(BatteryState.absent())

        with qtbot.waitSignal(controller.monitor.batteryUpdated, timeout=5000):
            controller.start()

        assert controller.status_viewmodel.caption.endswith("no battery")
        assert not controller.monitor.latest_state.present

    def test_tray_reflects_the_live_status(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(make_state(42, plugged=True))

        with qtbot.waitSignal(controller.monitor.batteryUpdated, timeout=5000):
            controller.start()

        assert "42%" in controller.tray.status_text
        assert controller.tray.tooltip_text.startswith("Battery Charge Notifier")
        assert controller.tray.is_paused is False


class TestUpperWarningAcceptance:
    def test_low_upper_limit_warns_once_then_stays_quiet(self, qtbot, build_app) -> None:
        """Acceptance criterion: upper limit at 3% yields exactly one warning."""
        controller, _manager, service = build_app(
            make_state(85, plugged=True),
            upper_limit=3,
            lower_limit=1,
            minimum_gap=1,
            rearm_gap=1,
        )

        warnings: list = []
        controller.monitor.warningRaised.connect(warnings.append)

        controller.start()
        qtbot.waitUntil(lambda: len(warnings) > 0, timeout=5000)
        first_poll_count = service.calls

        # Force many more polls; the state machine must stay quiet.
        for _ in range(25):
            controller.monitor.force_poll()
        qtbot.waitUntil(lambda: service.calls >= first_poll_count + 25, timeout=5000)
        # Let any spurious queued warning signal reach the connected slot.
        qtbot.wait(150)

        assert len(warnings) == 1
        assert warnings[0].kind is WarningKind.UPPER
        assert warnings[0].percent == 85
        assert warnings[0].message == "Battery at 85% \u2014 unplug the charger."

    def test_warning_popup_is_shown_and_then_reused(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(
            make_state(95, plugged=True), upper_limit=80, lower_limit=20
        )
        controller.start()

        qtbot.waitUntil(lambda: controller.notifier.is_popup_visible(), timeout=5000)
        first = controller.notifier.window
        assert first is not None
        assert first.isVisible()
        assert "95%" in first.findChild(QLabel, "percent").text()
        assert first.findChild(QLabel, "headline").text() == "Unplug the charger"

        # A second warning must update the same window, not stack a new one.
        controller.notifier.present_test_warning(WarningKind.LOWER, 12)
        assert controller.notifier.window is first
        assert first.findChild(QLabel, "headline").text() == "Plug in the charger"
        assert "12%" in first.findChild(QLabel, "percent").text()

    def test_lower_warning_when_running_on_battery(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(
            make_state(8, plugged=False), upper_limit=80, lower_limit=20
        )

        with qtbot.waitSignal(controller.monitor.warningRaised, timeout=5000) as blocker:
            controller.start()

        assert blocker.args[0].kind is WarningKind.LOWER
        assert blocker.args[0].message == "Battery at 8% \u2014 plug in the charger."


class TestLiveConfiguration:
    def test_settings_change_applies_without_restart(self, qtbot, build_app) -> None:
        controller, manager, _service = build_app(
            make_state(50, plugged=True), upper_limit=80, lower_limit=20
        )
        controller.start()
        qtbot.waitUntil(lambda: controller.monitor.latest_state is not None, timeout=5000)

        assert controller.status_viewmodel.action is None

        manager.update(upper_limit=40, minimum_gap=10)

        assert controller.config.upper_limit == 40
        assert controller.status_viewmodel.action == "unplug"
        assert "unplug" in controller.tray.status_text

    def test_pause_monitoring_stops_the_timer(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(make_state(85, plugged=True))
        controller.start()
        qtbot.waitUntil(lambda: controller.monitor.latest_state is not None, timeout=5000)

        controller.toggle_monitoring()
        assert controller.config.monitoring_enabled is False
        assert "paused" in controller.status_viewmodel.caption

        controller.toggle_monitoring()
        assert controller.config.monitoring_enabled is True

    def test_invalid_settings_are_rejected_and_file_is_untouched(
        self, qtbot, build_app
    ) -> None:
        controller, manager, _service = build_app(make_state(50, plugged=False))
        controller.start()
        before = json.loads(manager.path.read_text(encoding="utf-8"))

        controller.settings_viewmodel.stage("lower_limit", 95)  # gap now below the minimum

        assert controller.config.lower_limit == 20
        after = json.loads(manager.path.read_text(encoding="utf-8"))
        assert after == before
        assert "upper_limit" in controller.settings_viewmodel.issues

    def test_valid_settings_are_persisted_from_the_dialog_viewmodel(
        self, qtbot, build_app
    ) -> None:
        controller, manager, _service = build_app(make_state(50, plugged=False))
        controller.start()

        assert controller.settings_viewmodel.stage("upper_limit", 70) is True
        assert manager.load().upper_limit == 70

    def test_open_settings_creates_a_single_dialog(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(make_state(50, plugged=False))
        controller.start()

        controller.open_settings()
        first = controller.settings_dialog
        controller.open_settings()
        assert first is not None
        assert controller.settings_dialog is first
        first.close()


class TestShutdown:
    def test_shutdown_stops_the_monitor(self, qtbot, build_app) -> None:
        controller, _manager, _service = build_app(make_state(50, plugged=False))
        controller.start()
        qtbot.waitUntil(lambda: controller.monitor.is_running, timeout=5000)

        controller.shutdown()
        assert not controller.monitor.is_running
