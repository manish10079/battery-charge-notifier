"""Application wiring: dependency injection and signal plumbing.

This is the only module that knows about every other one. It constructs the
services, injects them into the ViewModels, connects the signals and exposes a
handful of commands for :mod:`battery_charge_notifier.main` and the tests to drive.

Keeping the composition here means the widgets, the ViewModels and the services
all stay independently testable: nothing reaches out for a global.
"""

from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QApplication

from .app_config import AppConfig, ConfigManager
from .battery_service import BatteryService, BatteryState, PsutilBatteryService
from .monitor import BatteryMonitor, WarningKind
from .notifier import Notifier
from .settings_dialog import SettingsDialog
from .single_instance import COMMAND_SHOW_SETTINGS, SingleInstance
from .startup import StartupService, create_startup_service
from .tray import TrayIcon
from .viewmodels.settings import SettingsViewModel
from .viewmodels.status import StatusViewModel

logger = logging.getLogger(__name__)


class AppController(QObject):
    """Owns the application's object graph and keeps it in sync."""

    #: Emitted when the application should exit.
    quitRequested = Signal()

    def __init__(
        self,
        app: QApplication,
        *,
        battery_service: BatteryService | None = None,
        config_manager: ConfigManager | None = None,
        startup_service: StartupService | None = None,
        single_instance: SingleInstance | None = None,
        sync_startup: bool = True,
        parent: QObject | None = None,
    ) -> None:
        """Build the object graph.

        Every collaborator is injectable so that tests can run the whole
        application against synthetic battery data, a temporary configuration
        file and a no-op autostart service.

        Args:
            app: The running ``QApplication``.
            battery_service: Battery reader. Defaults to :class:`PsutilBatteryService`.
            config_manager: Configuration store. Defaults to the platform path.
            startup_service: Autostart integration. Defaults to the platform one.
            single_instance: Inter-process lock, if one was acquired.
            sync_startup: Whether to reconcile the autostart registration with the
                configuration on :meth:`start`. Disable to avoid touching the
                host's login items.
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._app = app
        self._sync_startup = sync_startup
        self._single_instance = single_instance
        self._startup = startup_service or create_startup_service()

        self._config_manager = config_manager or ConfigManager()
        self._config = self._config_manager.load()
        if self._config_manager.load_issues:
            logger.warning(
                "Repaired %d configuration value(s) on load", len(self._config_manager.load_issues)
            )

        self._battery_service = battery_service or PsutilBatteryService()

        self._status_viewmodel = StatusViewModel(self._config, self)
        self._settings_viewmodel = SettingsViewModel(self._config_manager, self)
        self._monitor = BatteryMonitor(self._battery_service, self._config, self)
        self._tray = TrayIcon(self._status_viewmodel, self)
        self._notifier = Notifier(self._config, self._tray.icon, self)

        self._settings_dialog: SettingsDialog | None = None

        self._connect()

    # -- accessors (used by tests and by main) -----------------------------
    @property
    def config_manager(self) -> ConfigManager:
        """The configuration store."""
        return self._config_manager

    @property
    def config(self) -> AppConfig:
        """The configuration currently in force."""
        return self._config

    @property
    def monitor(self) -> BatteryMonitor:
        """The background battery monitor."""
        return self._monitor

    @property
    def tray(self) -> TrayIcon:
        """The tray icon."""
        return self._tray

    @property
    def notifier(self) -> Notifier:
        """The warning dispatcher."""
        return self._notifier

    @property
    def status_viewmodel(self) -> StatusViewModel:
        """The tray status ViewModel."""
        return self._status_viewmodel

    @property
    def settings_viewmodel(self) -> SettingsViewModel:
        """The settings ViewModel."""
        return self._settings_viewmodel

    @property
    def settings_dialog(self) -> SettingsDialog | None:
        """The settings dialog, once :meth:`open_settings` has been called."""
        return self._settings_dialog

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        """Show the tray icon, start monitoring and apply autostart preferences."""
        if self._sync_startup:
            self._reconcile_startup(self._config.launch_at_startup)
        self._tray.show()
        self._monitor.start()
        logger.info("Battery Charge Notifier started (limits %s/%s)", self._config.upper_limit, self._config.lower_limit)

    def shutdown(self) -> None:
        """Stop monitoring and release the single-instance lock."""
        self._monitor.stop()
        self._tray.hide()
        if self._single_instance is not None:
            self._single_instance.release()

    # -- commands ----------------------------------------------------------
    def open_settings(self) -> None:
        """Show the settings dialog, creating it on first use."""
        if self._settings_dialog is None:
            self._settings_dialog = SettingsDialog(self._settings_viewmodel)
        self._settings_dialog.show()
        self._settings_dialog.raise_()
        self._settings_dialog.activateWindow()

    def test_warning(self, kind: WarningKind) -> None:
        """Preview a warning popup without waiting for the battery.

        Args:
            kind: Which warning to demonstrate.
        """
        self._notifier.present_test_warning(kind, self._preview_percent(kind))

    def set_monitoring_enabled(self, enabled: bool) -> None:
        """Pause or resume monitoring.

        Args:
            enabled: The requested state.
        """
        self._config_manager.update(monitoring_enabled=enabled)

    def toggle_monitoring(self) -> None:
        """Flip the pause switch."""
        self.set_monitoring_enabled(not self._config.monitoring_enabled)

    # -- wiring ------------------------------------------------------------
    def _connect(self) -> None:
        """Connect every signal in the graph."""
        self._monitor.batteryUpdated.connect(self._on_battery_updated)
        self._monitor.warningRaised.connect(self._notifier.notify)

        self._notifier.snoozeRequested.connect(self._on_snooze)
        self._notifier.settingsRequested.connect(self.open_settings)

        self._tray.settingsRequested.connect(self.open_settings)
        self._tray.testWarningRequested.connect(self._on_test_warning)
        self._tray.monitoringToggleRequested.connect(self.set_monitoring_enabled)
        self._tray.quitRequested.connect(self.quitRequested)

        self._config_manager.changed.connect(self._on_config_changed)

        if self._single_instance is not None:
            self._single_instance.messageReceived.connect(self._on_instance_message)

    def _on_battery_updated(self, state: BatteryState) -> None:
        """Feed a fresh sample to the tray status."""
        self._status_viewmodel.update_battery(state)

    def _on_snooze(self, kind: WarningKind) -> None:
        """Forward a snooze request to the background worker."""
        self._monitor.snooze(kind)

    def _on_test_warning(self, kind: str) -> None:
        """Translate the tray's menu command into a preview."""
        self.test_warning(WarningKind(kind))

    def _on_instance_message(self, message: str) -> None:
        """Handle a command sent by a second launch."""
        if message == COMMAND_SHOW_SETTINGS:
            self.open_settings()

    def _on_config_changed(self, config: AppConfig) -> None:
        """Apply a committed configuration everywhere, live."""
        previous = self._config
        self._config = config

        self._monitor.apply_config(config)
        self._notifier.apply_config(config)
        self._status_viewmodel.apply_config(config)

        if config.launch_at_startup != previous.launch_at_startup:
            self._reconcile_startup(config.launch_at_startup)

    # -- internals ---------------------------------------------------------
    def _preview_percent(self, kind: WarningKind) -> int:
        """Pick a sensible charge level for a previewed warning."""
        if kind is WarningKind.UPPER:
            return self._config.upper_limit
        return self._config.lower_limit

    def _reconcile_startup(self, enabled: bool) -> None:
        """Make the platform autostart registration match *enabled*."""
        try:
            if self._startup.is_enabled() != enabled:
                self._startup.set_enabled(enabled)
        except Exception:  # noqa: BLE001 - autostart must never break startup
            logger.warning("Could not update the launch-at-login setting", exc_info=True)


def build_controller(
    app: QApplication,
    *,
    battery_service: BatteryService | None = None,
    config_path: str | None = None,
    startup_service: StartupService | None = None,
    sync_startup: bool = False,
) -> AppController:
    """Assemble an :class:`AppController`, injecting test doubles when given.

    Args:
        app: The running ``QApplication``.
        battery_service: Battery reader to inject.
        config_path: Configuration file to use instead of the platform default.
        startup_service: Autostart integration to inject.
        sync_startup: Whether the controller may touch the host's login items.

    Returns:
        A ready, but not yet started, controller.
    """
    manager = ConfigManager(config_path) if config_path is not None else None
    return AppController(
        app,
        battery_service=battery_service,
        config_manager=manager,
        startup_service=startup_service,
        sync_startup=sync_startup,
    )


__all__ = ["AppController", "build_controller"]
