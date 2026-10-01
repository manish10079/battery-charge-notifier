"""Tests for the ViewModels and the warning dispatcher."""

from __future__ import annotations

import time
from pathlib import Path

import pytest

from battery_charge_notifier.app_config import AppConfig, ConfigManager
from battery_charge_notifier.battery_service import BatteryState
from battery_charge_notifier.monitor import WarningEvent, WarningKind
from battery_charge_notifier.notifier import Notifier
from battery_charge_notifier.viewmodels.settings import SettingsViewModel
from battery_charge_notifier.viewmodels.status import StatusViewModel, format_duration
from battery_charge_notifier.viewmodels.warning import WarningViewModel


def plugged(percent: int) -> BatteryState:
    """A plugged-in battery state."""
    return BatteryState(percent=percent, plugged=True, charging=percent < 100)


def unplugged(percent: int) -> BatteryState:
    """A battery state running on battery power."""
    return BatteryState(percent=percent, plugged=False, charging=False)


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------
class TestStatusViewModel:
    def test_reports_no_battery_before_the_first_sample(self) -> None:
        vm = StatusViewModel()
        assert vm.caption == "Status  ·  no battery"
        assert vm.has_battery is False
        assert vm.icon_name.endswith("paused.png")

    def test_summarises_a_healthy_reading(self) -> None:
        vm = StatusViewModel(AppConfig())
        vm.update_battery(unplugged(55))
        assert "55%" in vm.caption
        assert vm.action is None
        assert vm.icon_name == "tray_ok.png"

    def test_upper_zone_asks_the_user_to_unplug(self) -> None:
        vm = StatusViewModel(AppConfig(upper_limit=80, lower_limit=20))
        vm.update_battery(plugged(85))
        assert vm.action == "unplug"
        assert "unplug" in vm.caption
        assert vm.icon_name == "tray_unplug.png"

    def test_lower_zone_asks_the_user_to_plug_in(self) -> None:
        vm = StatusViewModel(AppConfig(upper_limit=80, lower_limit=20))
        vm.update_battery(unplugged(15))
        assert vm.action == "plug_in"
        assert vm.icon_name == "tray_plug.png"

    def test_no_action_when_plugged_at_a_low_level(self) -> None:
        """Plugged in below the upper limit is perfectly fine."""
        vm = StatusViewModel(AppConfig(upper_limit=80, lower_limit=20))
        vm.update_battery(plugged(10))
        assert vm.action is None

    def test_paused_monitoring_suppresses_the_action(self) -> None:
        vm = StatusViewModel(AppConfig(upper_limit=80, lower_limit=20, monitoring_enabled=False))
        vm.update_battery(unplugged(5))
        assert vm.action is None
        assert vm.caption.endswith("paused")

    def test_tooltip_describes_limits_and_polling(self) -> None:
        vm = StatusViewModel(AppConfig(upper_limit=75, lower_limit=25, poll_interval_seconds=30))
        vm.update_battery(unplugged(50))
        tooltip = vm.tooltip
        assert "unplug at 75%" in tooltip
        assert "plug in at 25%" in tooltip
        assert "Polling every 30 s" in tooltip

    def test_end_of_sample_is_announced(self) -> None:
        vm = StatusViewModel()
        vm.update_battery(BatteryState(percent=50, plugged=False, charging=False, seconds_left=5400))
        assert "1 h 30 min remaining" in vm.tooltip

    def test_status_changed_signal_fires(self, qtbot) -> None:
        vm = StatusViewModel()
        with qtbot.waitSignal(vm.statusChanged, timeout=1000):
            vm.update_battery(unplugged(50))


class TestFormatDuration:
    @pytest.mark.parametrize(
        ("seconds", "expected"),
        [
            (None, ""),
            (0, ""),
            (-5, ""),
            (30, "1 min"),
            (120, "2 min"),
            (5400, "1 h 30 min"),
            (7200, "2 h 0 min"),
        ],
    )
    def test_formats(self, seconds: int | None, expected: str) -> None:
        assert format_duration(seconds) == expected


# ---------------------------------------------------------------------------
# Warning
# ---------------------------------------------------------------------------
class TestWarningViewModel:
    def test_no_content_before_the_first_warning(self) -> None:
        assert WarningViewModel().content is None

    def test_upper_content_is_shaped_for_the_view(self) -> None:
        vm = WarningViewModel(AppConfig(upper_limit=80, lower_limit=20))
        content = vm.show(WarningEvent(WarningKind.UPPER, 87, time.monotonic()))
        assert content.headline == "Unplug the charger"
        assert content.detail == "Battery at 87% \u2014 unplug the charger."
        assert content.percent == 87
        assert content.action == "unplug"
        assert content.icon_name == "tray_unplug.png"
        assert content.snooze_label == "Snooze 15 min"
        assert content.is_upper is True

    def test_lower_content_is_shaped_for_the_view(self) -> None:
        vm = WarningViewModel(AppConfig(upper_limit=80, lower_limit=20))
        content = vm.show(WarningEvent(WarningKind.LOWER, 12, time.monotonic()))
        assert content.headline == "Plug in the charger"
        assert content.action == "plug_in"
        assert content.icon_name == "tray_plug.png"

    def test_snooze_caption_follows_the_configuration(self) -> None:
        vm = WarningViewModel(AppConfig(snooze_minutes=7))
        content = vm.show(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))
        assert content.snooze_label == "Snooze 7 min"

    def test_reconfiguring_refreshes_the_visible_content(self, qtbot) -> None:
        vm = WarningViewModel(AppConfig(snooze_minutes=15))
        vm.show(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))
        with qtbot.waitSignal(vm.contentChanged, timeout=1000) as blocker:
            vm.apply_config(AppConfig(snooze_minutes=3))
        assert blocker.args[0].snooze_label == "Snooze 3 min"

    def test_actions_emit_the_expected_signals(self, qtbot) -> None:
        vm = WarningViewModel()
        vm.show(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))

        with qtbot.waitSignal(vm.snoozeRequested, timeout=1000) as snoozed:
            vm.snooze()
        assert snoozed.args[0] is WarningKind.UPPER

        with qtbot.waitSignal(vm.settingsRequested, timeout=1000):
            vm.open_settings()

        with qtbot.waitSignal(vm.dismissed, timeout=1000):
            vm.dismiss()

    def test_snooze_before_any_warning_is_harmless(self) -> None:
        WarningViewModel().snooze()


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------
class TestSettingsViewModel:
    @pytest.fixture
    def viewmodel(self, tmp_path: Path) -> SettingsViewModel:
        manager = ConfigManager(tmp_path / "config.json")
        manager.load()
        return SettingsViewModel(manager)

    def test_starts_from_the_persisted_configuration(self, viewmodel: SettingsViewModel) -> None:
        assert viewmodel.value("upper_limit") == 80
        assert viewmodel.issues == {}

    def test_accepts_a_valid_edit(self, viewmodel: SettingsViewModel, qtbot) -> None:
        with qtbot.waitSignal(viewmodel.accepted, timeout=1000):
            assert viewmodel.stage("upper_limit", 70) is True
        assert viewmodel.config.upper_limit == 70

    def test_rejects_an_edit_that_breaks_the_cross_field_rule(
        self, viewmodel: SettingsViewModel, qtbot
    ) -> None:
        with qtbot.waitSignal(viewmodel.rejected, timeout=1000) as blocker:
            assert viewmodel.stage("lower_limit", 90) is False
        assert "upper_limit" in blocker.args[0]
        assert viewmodel.config.lower_limit == 20

    def test_rejects_an_out_of_range_value(self, viewmodel: SettingsViewModel) -> None:
        assert viewmodel.stage("upper_limit", 500) is False
        assert "upper_limit" in viewmodel.issues

    def test_recovers_after_a_valid_correction(self, viewmodel: SettingsViewModel) -> None:
        assert viewmodel.stage("lower_limit", 90) is False
        assert viewmodel.issues != {}
        assert viewmodel.stage("lower_limit", 30) is True
        assert viewmodel.issues == {}

    def test_stage_many_applies_a_group_atomically(self, viewmodel: SettingsViewModel) -> None:
        assert viewmodel.stage_many({"upper_limit": 60, "lower_limit": 30}) is True
        assert viewmodel.config.upper_limit == 60
        assert viewmodel.config.lower_limit == 30

    def test_restore_defaults(self, viewmodel: SettingsViewModel) -> None:
        viewmodel.stage("upper_limit", 70)
        assert viewmodel.reset_to_defaults() is True
        assert viewmodel.config == AppConfig()

    def test_external_change_reloads_the_staged_values(
        self, viewmodel: SettingsViewModel, tmp_path: Path, qtbot
    ) -> None:
        with qtbot.waitSignal(viewmodel.reloaded, timeout=1000) as blocker:
            viewmodel._manager.update(upper_limit=65)  # noqa: SLF001 - acting as the tray would
        assert blocker.args[0].upper_limit == 65
        assert viewmodel.value("upper_limit") == 65

    def test_fields_expose_the_schema(self, viewmodel: SettingsViewModel) -> None:
        keys = [spec.key for spec in viewmodel.fields]
        assert keys[0] == "upper_limit"
        assert "notification_mode" in keys


# ---------------------------------------------------------------------------
# Notifier
# ---------------------------------------------------------------------------
class TestNotifier:
    def test_popup_mode_shows_the_window(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="popup"))
        notifier.notify(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))
        assert notifier.is_popup_visible() is True
        notifier.dismiss()

    def test_tray_only_mode_skips_the_popup(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="tray"))
        notifier.notify(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))
        assert notifier.is_popup_visible() is False

    def test_repeated_warnings_reuse_one_window(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="popup"))
        notifier.notify(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))
        first = notifier.window
        notifier.notify(WarningEvent(WarningKind.LOWER, 10, time.monotonic()))
        assert notifier.window is first

    def test_snooze_hides_the_popup_and_is_forwarded(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="popup"))
        notifier.notify(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))

        with qtbot.waitSignal(notifier.snoozeRequested, timeout=1000) as blocker:
            notifier.viewmodel.snooze()

        assert blocker.args[0] is WarningKind.UPPER
        assert notifier.is_popup_visible() is False

    def test_dismiss_hides_the_popup(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="popup"))
        notifier.notify(WarningEvent(WarningKind.UPPER, 90, time.monotonic()))

        with qtbot.waitSignal(notifier.dismissed, timeout=1000):
            notifier.viewmodel.dismiss()

        assert notifier.is_popup_visible() is False

    def test_settings_request_is_forwarded(self, qtbot) -> None:
        notifier = Notifier()
        with qtbot.waitSignal(notifier.settingsRequested, timeout=1000):
            notifier.viewmodel.open_settings()

    def test_test_warning_follows_popup_mode(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="popup"))
        notifier.present_test_warning(WarningKind.LOWER, 9)
        assert notifier.is_popup_visible() is True
        notifier.dismiss()

    def test_test_warning_follows_tray_mode(self, qtbot) -> None:
        notifier = Notifier(AppConfig(notification_mode="tray"))
        notifier.present_test_warning(WarningKind.LOWER, 9)
        assert notifier.is_popup_visible() is False
