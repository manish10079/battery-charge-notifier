"""Tests for the configuration schema, validation and persistence."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from battery_charge_notifier.app_config import (
    AppConfig,
    ConfigManager,
    ConfigValidationError,
    FIELDS,
    config_from_mapping,
    default_config_dir,
    default_config_path,
    validate,
)


@pytest.fixture
def manager(tmp_path: Path) -> ConfigManager:
    """A manager bound to a throwaway config file."""
    return ConfigManager(tmp_path / "config.json")


# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------
class TestDefaults:
    def test_documented_defaults(self) -> None:
        config = AppConfig()
        assert config.upper_limit == 80
        assert config.lower_limit == 20
        assert config.rearm_gap == 5
        assert config.minimum_gap == 10
        assert config.snooze_minutes == 15
        assert config.poll_interval_seconds == 60
        assert config.popup_timeout_seconds == 0
        assert config.monitoring_enabled is True
        assert config.launch_at_startup is True
        assert config.notification_mode == "popup"
        assert config.theme == "system"

    def test_every_schema_field_exists_on_the_config(self) -> None:
        for spec in FIELDS:
            assert hasattr(AppConfig(), spec.key), spec.key

    def test_derived_values(self) -> None:
        config = AppConfig(upper_limit=80, lower_limit=20, rearm_gap=5, snooze_minutes=15)
        assert config.upper_rearm_point == 75
        assert config.lower_rearm_point == 25
        assert config.poll_interval_ms == 60_000
        assert config.snooze_seconds == 900


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
class TestValidation:
    def test_defaults_are_valid(self) -> None:
        assert validate(AppConfig()) == ()

    @pytest.mark.parametrize("limit", [0, -5, 101, 200])
    def test_upper_limit_out_of_range(self, limit: int) -> None:
        issues = validate(AppConfig(upper_limit=limit))
        assert any(issue.field == "upper_limit" for issue in issues)

    @pytest.mark.parametrize("limit", [0, 101])
    def test_lower_limit_out_of_range(self, limit: int) -> None:
        issues = validate(AppConfig(lower_limit=limit))
        assert any(issue.field == "lower_limit" for issue in issues)

    def test_rejects_upper_below_lower(self) -> None:
        issues = validate(AppConfig(upper_limit=30, lower_limit=60))
        assert any(issue.field == "upper_limit" for issue in issues)

    def test_rejects_upper_equal_to_lower(self) -> None:
        assert validate(AppConfig(upper_limit=50, lower_limit=50)) != ()

    def test_rejects_gap_smaller_than_the_minimum(self) -> None:
        issues = validate(AppConfig(upper_limit=55, lower_limit=50, minimum_gap=10))
        assert any("at least 10%" in issue.message for issue in issues)

    def test_accepts_gap_exactly_equal_to_the_minimum(self) -> None:
        assert validate(AppConfig(upper_limit=60, lower_limit=50, minimum_gap=10)) == ()

    def test_minimum_gap_itself_is_configurable(self) -> None:
        assert validate(AppConfig(upper_limit=55, lower_limit=50, minimum_gap=5)) == ()
        assert validate(AppConfig(upper_limit=52, lower_limit=50, minimum_gap=5)) != ()

    def test_rejects_unknown_notification_mode(self) -> None:
        bad = AppConfig(upper_limit=80, lower_limit=20)
        object.__setattr__(bad, "notification_mode", "carrier-pigeon")
        assert any(issue.field == "notification_mode" for issue in validate(bad))

    def test_rejects_boolean_where_a_number_is_expected(self) -> None:
        assert validate(AppConfig(upper_limit=True)) != ()

    def test_rejects_zero_poll_interval(self) -> None:
        assert any(
            issue.field == "poll_interval_seconds"
            for issue in validate(AppConfig(poll_interval_seconds=0))
        )

    def test_error_lists_messages_per_field(self) -> None:
        error = ConfigValidationError(validate(AppConfig(upper_limit=101)))
        assert "upper_limit" in error.messages_by_field()


# ---------------------------------------------------------------------------
# Coercion / repair
# ---------------------------------------------------------------------------
class TestRepair:
    def test_unknown_keys_are_ignored(self) -> None:
        config, issues = config_from_mapping({"upper_limit": 70, "nonsense": 1})
        assert config.upper_limit == 70
        assert not any(issue.field == "nonsense" for issue in issues)

    def test_missing_keys_use_defaults(self) -> None:
        config, issues = config_from_mapping({"upper_limit": 70})
        assert config.upper_limit == 70
        assert config.lower_limit == 20
        assert issues == ()

    def test_out_of_range_values_are_clamped_and_reported(self) -> None:
        config, issues = config_from_mapping({"upper_limit": 500, "lower_limit": -3})
        assert config.upper_limit == 100
        assert config.lower_limit == 1
        assert {issue.field for issue in issues} == {"upper_limit", "lower_limit"}

    def test_wrong_types_fall_back_to_defaults(self) -> None:
        config, issues = config_from_mapping({"upper_limit": "banana", "lower_limit": None})
        assert config.upper_limit == 80
        assert config.lower_limit == 20
        assert {issue.field for issue in issues} == {"upper_limit", "lower_limit"}

    def test_numeric_strings_are_accepted(self) -> None:
        config, issues = config_from_mapping({"upper_limit": "70", "lower_limit": "30"})
        assert config.upper_limit == 70
        assert config.lower_limit == 30
        assert {issue.field for issue in issues} == {"upper_limit", "lower_limit"}

    def test_string_booleans_are_accepted(self) -> None:
        config, _ = config_from_mapping({"monitoring_enabled": "false"})
        assert config.monitoring_enabled is False

    def test_cross_field_violation_is_repaired_when_loaded(self, manager: ConfigManager) -> None:
        """A hand-edited file that breaks the cross-field rule must not brick startup."""
        manager.path.parent.mkdir(parents=True, exist_ok=True)
        manager.path.write_text(
            json.dumps({"upper_limit": 10, "lower_limit": 90}), encoding="utf-8"
        )
        assert manager.load() == AppConfig()
        assert any(issue.field == "upper_limit" for issue in manager.load_issues)


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------
class TestPersistence:
    def test_missing_file_yields_defaults(self, manager: ConfigManager) -> None:
        assert manager.load() == AppConfig()
        assert manager.load_issues == ()
        assert not manager.path.exists()

    def test_save_then_load_roundtrip(self, manager: ConfigManager) -> None:
        saved = AppConfig(upper_limit=70, lower_limit=30, rearm_gap=8, snooze_minutes=5)
        manager.save(saved)
        assert manager.load() == saved

    def test_saved_file_is_valid_json_with_every_key(self, manager: ConfigManager) -> None:
        manager.save(AppConfig())
        payload = json.loads(manager.path.read_text(encoding="utf-8"))
        assert set(payload) == {spec.key for spec in FIELDS}

    def test_save_rejects_invalid_configuration(self, manager: ConfigManager) -> None:
        with pytest.raises(ConfigValidationError) as excinfo:
            manager.save(AppConfig(upper_limit=10, lower_limit=90))
        assert excinfo.value.issues
        assert not manager.path.exists()

    def test_corrupt_json_recovers_with_defaults(self, manager: ConfigManager) -> None:
        manager.path.parent.mkdir(parents=True, exist_ok=True)
        manager.path.write_text("{ this is not json", encoding="utf-8")
        assert manager.load() == AppConfig()
        assert any(issue.field == "__file__" for issue in manager.load_issues)

    def test_non_object_json_recovers_with_defaults(self, manager: ConfigManager) -> None:
        manager.path.parent.mkdir(parents=True, exist_ok=True)
        manager.path.write_text("[1, 2, 3]", encoding="utf-8")
        assert manager.load() == AppConfig()
        assert any(issue.field == "__file__" for issue in manager.load_issues)

    def test_write_is_atomic_and_leaves_no_temp_files(self, manager: ConfigManager) -> None:
        manager.save(AppConfig())
        manager.save(AppConfig(upper_limit=75))
        leftovers = [p.name for p in manager.path.parent.iterdir() if p.name != "config.json"]
        assert leftovers == []
        assert manager.load().upper_limit == 75

    def test_save_creates_missing_directories(self, tmp_path: Path) -> None:
        nested = ConfigManager(tmp_path / "deep" / "nested" / "config.json")
        nested.save(AppConfig())
        assert nested.path.exists()


# ---------------------------------------------------------------------------
# Manager behaviour
# ---------------------------------------------------------------------------
class TestConfigManager:
    def test_update_persists_and_emits(self, manager: ConfigManager, qtbot) -> None:
        manager.load()
        with qtbot.waitSignal(manager.changed, timeout=1000) as blocker:
            config = manager.update(upper_limit=75)
        assert config.upper_limit == 75
        assert blocker.args[0].upper_limit == 75
        assert json.loads(manager.path.read_text(encoding="utf-8"))["upper_limit"] == 75

    def test_update_rejects_invalid_change_without_writing(
        self, manager: ConfigManager
    ) -> None:
        manager.load()
        with pytest.raises(ConfigValidationError):
            manager.update(lower_limit=95)  # would leave a gap below the minimum
        assert not manager.path.exists()

    def test_update_rejects_unknown_field(self, manager: ConfigManager) -> None:
        with pytest.raises(KeyError):
            manager.update(colour="blue")

    def test_reset_restores_defaults(self, manager: ConfigManager) -> None:
        manager.load()
        manager.update(upper_limit=70)
        assert manager.reset() == AppConfig()

    def test_update_does_not_emit_when_nothing_changed(self, manager: ConfigManager) -> None:
        manager.load()
        received: list[AppConfig] = []
        manager.changed.connect(received.append)
        manager.update(upper_limit=80)  # already the default
        assert received == []

    def test_load_caches_config(self, manager: ConfigManager) -> None:
        manager.save(AppConfig(upper_limit=65))
        assert ConfigManager(manager.path).load().upper_limit == 65


# ---------------------------------------------------------------------------
# Platform paths
# ---------------------------------------------------------------------------
class TestPaths:
    def test_windows_uses_appdata(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path))
        assert default_config_dir() == tmp_path / "Battery Charge Notifier"
        assert default_config_path().name == "config.json"

    def test_macos_uses_application_support(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "darwin")
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        expected = tmp_path / "Library" / "Application Support" / "Battery Charge Notifier"
        assert default_config_dir() == expected

    def test_linux_honours_xdg_config_home(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert default_config_dir() == tmp_path / "battery-charge-notifier"

    def test_linux_falls_back_to_dot_config(self, monkeypatch, tmp_path: Path) -> None:
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        assert default_config_dir() == tmp_path / ".config" / "battery-charge-notifier"

    def test_linux_directory_has_no_spaces(self, monkeypatch, tmp_path: Path) -> None:
        """The freedesktop convention is a lowercase, space-free identifier."""
        monkeypatch.setattr(sys, "platform", "linux")
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        assert " " not in default_config_dir().name

    def test_no_hardcoded_windows_path_in_module(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "battery_charge_notifier" / "app_config.py")
        text = source.read_text(encoding="utf-8")
        assert "C:\\" not in text
