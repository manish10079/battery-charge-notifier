"""ViewModel for the schema-driven settings dialog.

The dialog renders one control per :class:`~battery_charge_notifier.app_config.FieldSpec`
and reports edits here. This ViewModel stages the edits, validates the *whole*
resulting configuration on every keystroke, persists it when it is acceptable
and reports per-field messages when it is not. Persisting goes through
:class:`~battery_charge_notifier.app_config.ConfigManager`, so a valid change applies live
across the running application - no restart required.
"""

from __future__ import annotations

from typing import Any, Mapping

from PySide6.QtCore import QObject, Signal

from ..app_config import (
    AppConfig,
    ConfigManager,
    ConfigValidationError,
    FIELDS,
    FieldSpec,
    validate,
)


class SettingsViewModel(QObject):
    """Validates, stages and persists configuration edits."""

    #: Emitted with the committed :class:`AppConfig` after a successful edit.
    accepted = Signal(object)
    #: Emitted with a ``{field: message}`` mapping when an edit is rejected.
    rejected = Signal(object)
    #: Emitted with the authoritative :class:`AppConfig` when the staged values
    #: were replaced (for example because the tray changed the same setting).
    reloaded = Signal(object)

    def __init__(self, manager: ConfigManager, parent: QObject | None = None) -> None:
        """Create the ViewModel.

        Args:
            manager: The application's configuration manager.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._manager = manager
        self._draft: dict[str, Any] = manager.config.to_dict()
        self._issues: dict[str, str] = {}
        manager.changed.connect(self._on_external_change)

    # -- accessors ---------------------------------------------------------
    @property
    def fields(self) -> tuple[FieldSpec, ...]:
        """The schema, in display order."""
        return FIELDS

    @property
    def config(self) -> AppConfig:
        """The configuration currently persisted."""
        return self._manager.config

    @property
    def issues(self) -> Mapping[str, str]:
        """Per-field validation messages for the current staged values."""
        return dict(self._issues)

    def values(self) -> dict[str, Any]:
        """Return the staged (possibly uncommitted) values."""
        return dict(self._draft)

    def value(self, key: str) -> Any:
        """Return the staged value of *key*."""
        return self._draft[key]

    # -- edits -------------------------------------------------------------
    def stage(self, key: str, value: Any) -> bool:
        """Stage a single field and try to commit the result.

        Args:
            key: Schema key that changed.
            value: The newly entered value.

        Returns:
            ``True`` when the edit was accepted and persisted, ``False`` when it
            was rejected (in which case :attr:`issues` explains why).
        """
        self._draft[key] = value
        return self.commit()

    def stage_many(self, changes: Mapping[str, Any]) -> bool:
        """Stage several fields at once and try to commit the result.

        Args:
            changes: Mapping of schema keys to new values.

        Returns:
            ``True`` when the edit was accepted and persisted.
        """
        self._draft.update(changes)
        return self.commit()

    def commit(self) -> bool:
        """Validate and, if acceptable, persist the staged values.

        Returns:
            ``True`` when the values were persisted.
        """
        candidate = self._candidate()
        issues = validate(candidate)
        if issues:
            self._issues = {issue.field: issue.message for issue in issues}
            self.rejected.emit(dict(self._issues))
            return False

        self._issues = {}
        try:
            committed = self._manager.save(candidate)
        except ConfigValidationError as exc:  # pragma: no cover - guarded above
            self._issues = exc.messages_by_field()
            self.rejected.emit(dict(self._issues))
            return False

        self.accepted.emit(committed)
        return True

    def reset_to_defaults(self) -> bool:
        """Stage and persist the factory defaults.

        Returns:
            ``True`` when the defaults were persisted.
        """
        self._draft = AppConfig().to_dict()
        return self.commit()

    def refresh(self) -> None:
        """Re-read the staged values from the persisted configuration."""
        self._draft = self._manager.config.to_dict()
        self._issues = {}

    # -- internals ---------------------------------------------------------
    def _candidate(self) -> AppConfig:
        """Build an :class:`AppConfig` from the staged values."""
        defaults = AppConfig()
        values = {
            spec.key: self._draft.get(spec.key, getattr(defaults, spec.key))
            for spec in FIELDS
        }
        return AppConfig(**values)

    def _on_external_change(self, config: AppConfig) -> None:
        """Keep the staged values in step with changes made elsewhere."""
        if config.to_dict() == self._draft:
            # Our own commit; nothing to do.
            return
        self._draft = config.to_dict()
        self._issues = {}
        self.reloaded.emit(config)


__all__ = ["SettingsViewModel"]
