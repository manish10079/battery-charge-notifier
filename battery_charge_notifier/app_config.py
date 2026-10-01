"""Configuration schema, validation and persistence for Battery Charge Notifier.

The configuration is *schema driven*: :data:`FIELDS` is the single source of
truth that the settings dialog uses to build its controls, that
:class:`ConfigManager` uses to coerce and persist values, and that the test
suite uses to exercise validation. Adding a setting therefore means adding one
:class:`FieldSpec` and one dataclass field - no dialog code changes.

Storage location follows each platform's convention:

* Windows - ``%APPDATA%/Battery Charge Notifier/config.json``
* macOS - ``~/Library/Application Support/Battery Charge Notifier/config.json``
* Linux/BSD - ``$XDG_CONFIG_HOME/battery-charge-notifier/config.json``
  (falling back to ``~/.config/battery-charge-notifier/config.json``)

Writes are atomic (temp file + :func:`os.replace`) so a crash mid-save can
never leave a truncated configuration behind.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path
from typing import Any, Literal, Mapping

from PySide6.QtCore import QObject, Signal

APP_NAME = "Battery Charge Notifier"
#: Lowercase, space-free identifier for paths and keys that must stay portable.
APP_SLUG = "battery-charge-notifier"
CONFIG_FILENAME = "config.json"

NotificationMode = Literal["popup", "tray"]
FieldKind = Literal["int", "bool", "choice"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class FieldSpec:
    """Description of a single user-editable setting.

    Attributes:
        key: Attribute name on :class:`AppConfig`.
        label: Human readable label shown in the settings dialog.
        kind: Control/widget kind used to edit the value.
        default: Value used when the key is absent or unusable.
        minimum: Inclusive lower bound for ``int`` fields.
        maximum: Inclusive upper bound for ``int`` fields.
        suffix: Unit suffix rendered next to numeric controls.
        help_text: Explanatory sentence shown beneath the control.
        choices: Allowed values for ``choice`` fields.
    """

    key: str
    label: str
    kind: FieldKind
    default: Any
    minimum: int | None = None
    maximum: int | None = None
    suffix: str = ""
    help_text: str = ""
    choices: tuple[str, ...] = ()


FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        key="upper_limit",
        label="Upper limit",
        kind="int",
        default=80,
        minimum=1,
        maximum=100,
        suffix="%",
        help_text="Warn to unplug the charger once the battery reaches this level.",
    ),
    FieldSpec(
        key="lower_limit",
        label="Lower limit",
        kind="int",
        default=20,
        minimum=1,
        maximum=100,
        suffix="%",
        help_text="Warn to plug the charger in once the battery falls to this level.",
    ),
    FieldSpec(
        key="minimum_gap",
        label="Minimum gap",
        kind="int",
        default=10,
        minimum=1,
        maximum=99,
        suffix="%",
        help_text="The upper limit must stay at least this far above the lower limit.",
    ),
    FieldSpec(
        key="rearm_gap",
        label="Re-arm gap",
        kind="int",
        default=5,
        minimum=1,
        maximum=50,
        suffix="%",
        help_text=(
            "Hysteresis. After a warning fires it stays quiet until the battery "
            "moves back this far, which prevents nagging."
        ),
    ),
    FieldSpec(
        key="snooze_minutes",
        label="Snooze duration",
        kind="int",
        default=15,
        minimum=1,
        maximum=240,
        suffix=" min",
        help_text="How long the Snooze button suppresses the current warning.",
    ),
    FieldSpec(
        key="poll_interval_seconds",
        label="Poll interval",
        kind="int",
        default=60,
        minimum=5,
        maximum=3600,
        suffix=" s",
        help_text="How often the battery is sampled, on a background thread.",
    ),
    FieldSpec(
        key="monitoring_enabled",
        label="Monitoring enabled",
        kind="bool",
        default=True,
        help_text="Pause or resume all battery monitoring.",
    ),
    FieldSpec(
        key="launch_at_startup",
        label="Launch at login",
        kind="bool",
        default=True,
        help_text="Start Battery Charge Notifier automatically when you sign in.",
    ),
    FieldSpec(
        key="notification_mode",
        label="Notify via",
        kind="choice",
        default="popup",
        choices=("popup", "tray"),
        help_text=(
            "Choose one: an always-on-top popup window, or a system tray "
            "notification. Only the selected channel is used."
        ),
    ),
)

FIELDS_BY_KEY: Mapping[str, FieldSpec] = {spec.key: spec for spec in FIELDS}


# ---------------------------------------------------------------------------
# Value object
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class AppConfig:
    """An immutable snapshot of every user setting."""

    upper_limit: int = 80
    lower_limit: int = 20
    minimum_gap: int = 10
    rearm_gap: int = 5
    snooze_minutes: int = 15
    poll_interval_seconds: int = 60
    monitoring_enabled: bool = True
    launch_at_startup: bool = True
    notification_mode: NotificationMode = "popup"

    @property
    def upper_rearm_point(self) -> int:
        """Charge level the battery must fall below before the upper warning re-arms."""
        return self.upper_limit - self.rearm_gap

    @property
    def lower_rearm_point(self) -> int:
        """Charge level the battery must rise above before the lower warning re-arms."""
        return self.lower_limit + self.rearm_gap

    @property
    def poll_interval_ms(self) -> int:
        """Poll interval in milliseconds, as Qt timers expect it."""
        return self.poll_interval_seconds * 1000

    @property
    def snooze_seconds(self) -> int:
        """Snooze duration in seconds."""
        return self.snooze_minutes * 60

    def to_dict(self) -> dict[str, Any]:
        """Return the configuration as a JSON-serialisable mapping."""
        return asdict(self)


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class ValidationIssue:
    """A single rejected setting.

    Attributes:
        field: Key of the offending field, matching :data:`FIELDS`.
        message: User-facing explanation of why the value was rejected.
    """

    field: str
    message: str


class ConfigValidationError(ValueError):
    """Raised when a configuration is rejected by :func:`validate`."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = tuple(issues)
        detail = "; ".join(f"{issue.field}: {issue.message}" for issue in self.issues)
        super().__init__(f"Invalid configuration ({detail})")

    def messages_by_field(self) -> dict[str, str]:
        """Return the first message for each offending field."""
        result: dict[str, str] = {}
        for issue in self.issues:
            result.setdefault(issue.field, issue.message)
        return result


def validate(config: AppConfig) -> tuple[ValidationIssue, ...]:
    """Validate *config* against the schema and the cross-field rules.

    Args:
        config: The configuration to check.

    Returns:
        A tuple of :class:`ValidationIssue`; empty when the configuration is
        acceptable.
    """
    issues: list[ValidationIssue] = []

    for spec in FIELDS:
        value = getattr(config, spec.key, None)

        if spec.kind == "int":
            # bool is a subclass of int, so reject it explicitly.
            if isinstance(value, bool) or not isinstance(value, int):
                issues.append(
                    ValidationIssue(spec.key, f"{spec.label} must be a whole number.")
                )
                continue
            if spec.minimum is not None and value < spec.minimum:
                issues.append(
                    ValidationIssue(
                        spec.key,
                        f"{spec.label} must be at least {spec.minimum}{spec.suffix}.",
                    )
                )
            elif spec.maximum is not None and value > spec.maximum:
                issues.append(
                    ValidationIssue(
                        spec.key,
                        f"{spec.label} must be at most {spec.maximum}{spec.suffix}.",
                    )
                )
        elif spec.kind == "choice":
            if value not in spec.choices:
                allowed = ", ".join(spec.choices)
                issues.append(
                    ValidationIssue(spec.key, f"{spec.label} must be one of: {allowed}.")
                )
        elif spec.kind == "bool":
            if not isinstance(value, bool):
                issues.append(ValidationIssue(spec.key, f"{spec.label} must be yes or no."))

    # Cross-field rules. Skipped when one of the participating fields already
    # failed on its own, so the user is not shown a cascade of derived
    # complaints about the same edit.
    participants = {"upper_limit", "lower_limit", "minimum_gap"}
    if not (participants & {issue.field for issue in issues}):
        gap = config.minimum_gap
        if config.upper_limit <= config.lower_limit:
            issues.append(
                ValidationIssue(
                    "upper_limit",
                    f"The upper limit ({config.upper_limit}%) must be greater than "
                    f"the lower limit ({config.lower_limit}%).",
                )
            )
        elif config.upper_limit - config.lower_limit < gap:
            issues.append(
                ValidationIssue(
                    "upper_limit",
                    f"The upper limit must be at least {gap}% above the lower limit "
                    f"(currently {config.upper_limit - config.lower_limit}%).",
                )
            )

    return tuple(issues)


# ---------------------------------------------------------------------------
# Coercion helpers
# ---------------------------------------------------------------------------
def _coerce(spec: FieldSpec, raw: Any) -> Any:
    """Best-effort conversion of a stored value into the schema's type.

    Returns the spec default when *raw* cannot be interpreted at all.
    """
    if spec.kind == "int":
        if isinstance(raw, bool):
            return spec.default
        if isinstance(raw, int):
            return raw
        if isinstance(raw, float) and raw.is_integer():
            return int(raw)
        if isinstance(raw, str):
            try:
                return int(raw.strip())
            except ValueError:
                return spec.default
        return spec.default

    if spec.kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, (int, float)):
            return bool(raw)
        if isinstance(raw, str):
            lowered = raw.strip().lower()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return spec.default

    if spec.kind == "choice":
        if isinstance(raw, str) and raw in spec.choices:
            return raw
        return spec.default

    return spec.default


def config_from_mapping(data: Mapping[str, Any]) -> tuple[AppConfig, tuple[ValidationIssue, ...]]:
    """Build an :class:`AppConfig` from a raw mapping.

    Unknown keys are ignored, unreadable values fall back to their default, and
    out-of-range values are clamped so that a hand-edited or corrupt file can
    never prevent the application from starting.

    Args:
        data: Raw mapping, typically the decoded contents of ``config.json``.

    Returns:
        A ``(config, issues)`` pair. ``issues`` describes every value that had
        to be repaired; it is empty for a clean file.
    """
    issues: list[ValidationIssue] = []
    values: dict[str, Any] = {}

    for spec in FIELDS:
        if spec.key not in data:
            values[spec.key] = spec.default
            continue

        coerced = _coerce(spec, data[spec.key])
        if not _is_well_formed(spec, data[spec.key]):
            issues.append(
                ValidationIssue(
                    spec.key,
                    f"{spec.label} was invalid; using {spec.default}{spec.suffix}.",
                )
            )
        values[spec.key] = _clamp(spec, coerced)

    config = AppConfig(**values)
    return config, tuple(issues)


def _is_well_formed(spec: FieldSpec, raw: Any) -> bool:
    """Return whether *raw* is already a valid, in-range value for *spec*."""
    if spec.kind == "bool":
        return isinstance(raw, bool)
    if spec.kind == "choice":
        return isinstance(raw, str) and raw in spec.choices
    if spec.kind == "int":
        if isinstance(raw, bool) or not isinstance(raw, int):
            return False
        if spec.minimum is not None and raw < spec.minimum:
            return False
        if spec.maximum is not None and raw > spec.maximum:
            return False
        return True
    return False


def _clamp(spec: FieldSpec, value: Any) -> Any:
    """Force *value* inside the schema bounds for *spec*."""
    if spec.kind != "int":
        return value
    if spec.minimum is not None:
        value = max(spec.minimum, value)
    if spec.maximum is not None:
        value = min(spec.maximum, value)
    return value


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
def default_config_dir(app_name: str = APP_NAME, app_slug: str = APP_SLUG) -> Path:
    """Return the per-platform directory that holds Battery Charge Notifier's data.

    Windows and macOS follow their convention of a title-cased folder named after
    the product, while Linux follows the freedesktop convention of a lowercase,
    space-free identifier.

    Args:
        app_name: Directory name to use on Windows and macOS.
        app_slug: Directory name to use on Linux and BSD.

    Returns:
        The configuration directory. It is not created by this function.
    """
    if sys.platform.startswith("win"):
        root = os.environ.get("APPDATA")
        base = Path(root) if root else Path.home() / "AppData" / "Roaming"
        return base / app_name
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / app_name
    root = os.environ.get("XDG_CONFIG_HOME")
    base = Path(root) if root else Path.home() / ".config"
    return base / app_slug


def default_config_path(app_name: str = APP_NAME) -> Path:
    """Return the full path of ``config.json`` for this platform."""
    return default_config_dir(app_name) / CONFIG_FILENAME


# ---------------------------------------------------------------------------
# Manager
# ---------------------------------------------------------------------------
class ConfigManager(QObject):
    """Loads, validates, persists and broadcasts :class:`AppConfig` values.

    The manager caches the most recently loaded configuration so consumers can
    read :attr:`config` synchronously, and emits :attr:`changed` whenever a new
    configuration has been committed so the rest of the application can apply
    it live, without a restart.
    """

    #: Emitted with the new :class:`AppConfig` after a successful save.
    changed = Signal(object)

    def __init__(self, path: Path | str | None = None, parent: QObject | None = None) -> None:
        """Create a manager bound to *path*.

        Args:
            path: Explicit configuration file. Defaults to the platform path
                from :func:`default_config_path`.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._path = Path(path) if path is not None else default_config_path()
        self._config = AppConfig()
        self._load_issues: tuple[ValidationIssue, ...] = ()

    # -- accessors ---------------------------------------------------------
    @property
    def path(self) -> Path:
        """Path of the JSON file backing this manager."""
        return self._path

    @property
    def config(self) -> AppConfig:
        """The most recently loaded or saved configuration."""
        return self._config

    @property
    def load_issues(self) -> tuple[ValidationIssue, ...]:
        """Problems found while repairing the on-disk file during the last load."""
        return self._load_issues

    # -- operations --------------------------------------------------------
    def load(self) -> AppConfig:
        """Read the configuration from disk, repairing it when necessary.

        A missing file is not an error and yields the defaults. A corrupt file
        yields the defaults plus entries in :attr:`load_issues`; the application
        always starts.

        Returns:
            The loaded (and repaired) configuration.
        """
        data: Mapping[str, Any] = {}
        issues: list[ValidationIssue] = []

        try:
            text = self._path.read_text(encoding="utf-8")
        except FileNotFoundError:
            text = ""
        except OSError as exc:
            text = ""
            issues.append(
                ValidationIssue("__file__", f"Could not read {self._path}: {exc.strerror}")
            )

        if text.strip():
            try:
                decoded = json.loads(text)
            except json.JSONDecodeError as exc:
                issues.append(
                    ValidationIssue(
                        "__file__",
                        f"{self._path.name} is not valid JSON ({exc.msg}); using defaults.",
                    )
                )
            else:
                if isinstance(decoded, Mapping):
                    data = decoded
                else:
                    issues.append(
                        ValidationIssue(
                            "__file__",
                            f"{self._path.name} must contain a JSON object; using defaults.",
                        )
                    )

        config, coercion_issues = config_from_mapping(data)
        issues.extend(coercion_issues)

        # A repaired file must still satisfy the cross-field rules.
        cross_issues = validate(config)
        if cross_issues:
            issues.extend(cross_issues)
            config = AppConfig()

        self._config = config
        self._load_issues = tuple(issues)
        return config

    def save(self, config: AppConfig) -> AppConfig:
        """Validate, atomically write *config* to disk and commit it.

        This is the single place a configuration becomes current: it also emits
        :attr:`changed`, so callers never need to announce their own edits.

        Args:
            config: The configuration to persist.

        Returns:
            The same configuration, for convenient chaining.

        Raises:
            ConfigValidationError: If *config* is not acceptable.
        """
        issues = validate(config)
        if issues:
            raise ConfigValidationError(issues)

        previous = self._config
        self._write(config)
        self._config = config
        if config != previous:
            self.changed.emit(config)
        return config

    def update(self, config: AppConfig | None = None, /, **changes: Any) -> AppConfig:
        """Apply *changes*, persist the result and emit :attr:`changed`.

        Args:
            config: Optional base configuration. Defaults to the cached value.
            **changes: Field names to replace.

        Returns:
            The newly committed configuration.

        Raises:
            ConfigValidationError: If the resulting configuration is invalid.
        """
        base = self._config if config is None else config
        unknown = set(changes) - set(FIELDS_BY_KEY)
        if unknown:
            raise KeyError(f"Unknown configuration field(s): {', '.join(sorted(unknown))}")

        return self.save(replace(base, **changes))

    def reset(self) -> AppConfig:
        """Restore and persist the factory defaults."""
        return self.save(AppConfig())

    # -- internals ---------------------------------------------------------
    def _write(self, config: AppConfig) -> None:
        """Atomically write *config* to :attr:`path`, without touching the cache."""
        payload = json.dumps(config.to_dict(), indent=2, sort_keys=True)
        directory = self._path.parent
        directory.mkdir(parents=True, exist_ok=True)

        handle = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=directory,
            prefix=f".{self._path.name}.",
            suffix=".tmp",
            delete=False,
        )
        temp_path = Path(handle.name)
        try:
            with handle:
                handle.write(payload)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_path, self._path)
        except OSError:
            temp_path.unlink(missing_ok=True)
            raise


__all__ = [
    "APP_NAME",
    "AppConfig",
    "ConfigManager",
    "ConfigValidationError",
    "FIELDS",
    "FIELDS_BY_KEY",
    "FieldSpec",
    "ValidationIssue",
    "config_from_mapping",
    "default_config_dir",
    "default_config_path",
    "validate",
]
