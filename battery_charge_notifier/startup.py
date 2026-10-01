"""Per-platform "launch at login" integration.

Each platform gets a small implementation behind the same two-method interface,
plus a no-op fallback so unsupported systems never crash. Everything is
per-user: no implementation requires administrator rights, and the Windows
implementation only ever touches ``HKCU``.

* Windows - ``HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run``
* macOS - ``~/Library/LaunchAgents/com.batterychargenotifier.plist``
* Linux/BSD - ``$XDG_CONFIG_HOME/autostart/battery-charge-notifier.desktop``
"""

from __future__ import annotations

import logging
import os
import plistlib
import sys
from pathlib import Path
from typing import Protocol, runtime_checkable

logger = logging.getLogger(__name__)

APP_NAME = "Battery Charge Notifier"
WINDOWS_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
WINDOWS_VALUE_NAME = APP_NAME
MACOS_LABEL = "com.batterychargenotifier"
LINUX_DESKTOP_FILE = "battery-charge-notifier.desktop"


def _launch_command() -> str:
    """Return the command that starts the application in the background.

    Uses the interpreter and the module path rather than the ``battery_charge_notifier``
    console script, which is not guaranteed to be on ``PATH`` in every
    environment (notably a virtual environment launched from the desktop).
    """
    if getattr(sys, "frozen", False):
        # A PyInstaller build is its own executable.
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m battery_charge_notifier'


@runtime_checkable
class StartupService(Protocol):
    """Registers and unregisters the application for launch at login."""

    def is_enabled(self) -> bool:
        """Return whether launch-at-login is currently registered."""
        ...

    def set_enabled(self, enabled: bool) -> bool:
        """Register or unregister launch-at-login.

        Args:
            enabled: ``True`` to register, ``False`` to remove.

        Returns:
            ``True`` when the platform state now matches *enabled*.
        """
        ...


class NoopStartupService:
    """Fallback used on platforms without an implementation.

    Reports "disabled" and refuses to change anything, so the toggle in the
    settings dialog stays honest instead of silently doing nothing.
    """

    def is_enabled(self) -> bool:
        """Always ``False``; this platform cannot register autostart."""
        return False

    def set_enabled(self, enabled: bool) -> bool:
        """Report that the request could not be honoured."""
        if enabled:
            logger.info("Launch at login is not supported on this platform")
        return False


class WindowsStartupService:
    """Registers the application under the per-user ``Run`` registry key."""

    def __init__(self, value_name: str = WINDOWS_VALUE_NAME) -> None:
        """Create the service.

        Args:
            value_name: Registry value name to create under the ``Run`` key.
        """
        self._value_name = value_name

    def is_enabled(self) -> bool:
        """Return whether the ``Run`` value exists."""
        import winreg

        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY) as key:
                value, _ = winreg.QueryValueEx(key, self._value_name)
        except FileNotFoundError:
            return False
        except OSError:
            logger.warning("Could not read the Run registry key", exc_info=True)
            return False
        return bool(str(value).strip())

    def set_enabled(self, enabled: bool) -> bool:
        """Create or delete the ``Run`` value, then verify the result."""
        import winreg

        if enabled:
            command = _launch_command()
            try:
                with winreg.CreateKeyEx(
                    winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.SetValueEx(key, self._value_name, 0, winreg.REG_SZ, command)
            except OSError:
                logger.warning("Could not register launch at login", exc_info=True)
                return False
            logger.info("Registered launch at login: %s", command)
        else:
            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, WINDOWS_RUN_KEY, 0, winreg.KEY_SET_VALUE
                ) as key:
                    winreg.DeleteValue(key, self._value_name)
            except FileNotFoundError:
                return True  # Already absent.
            except OSError:
                logger.warning("Could not remove launch at login", exc_info=True)
                return False
            logger.info("Removed launch at login")

        return self.is_enabled() is enabled


class MacOSStartupService:
    """Writes a per-user launch agent plist."""

    def __init__(self, label: str = MACOS_LABEL) -> None:
        """Create the service.

        Args:
            label: Launch agent label, also used for the file name.
        """
        self._label = label
        self._path = Path.home() / "Library" / "LaunchAgents" / f"{label}.plist"

    @property
    def path(self) -> Path:
        """Location of the launch agent plist."""
        return self._path

    def is_enabled(self) -> bool:
        """Return whether the plist exists."""
        return self._path.is_file()

    def set_enabled(self, enabled: bool) -> bool:
        """Create or remove the plist."""
        if not enabled:
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove the launch agent", exc_info=True)
                return False
            return True

        payload = {
            "Label": self._label,
            "ProgramArguments": _launch_command().replace('"', "").split(),
            "RunAtLoad": True,
            "KeepAlive": False,
            "ProcessType": "Background",
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with self._path.open("wb") as handle:
                plistlib.dump(payload, handle)
        except OSError:
            logger.warning("Could not write the launch agent", exc_info=True)
            return False
        return True


class LinuxStartupService:
    """Writes a freedesktop autostart ``.desktop`` entry."""

    def __init__(self, filename: str = LINUX_DESKTOP_FILE) -> None:
        """Create the service.

        Args:
            filename: Name of the ``.desktop`` file.
        """
        root = os.environ.get("XDG_CONFIG_HOME")
        base = Path(root) if root else Path.home() / ".config"
        self._path = base / "autostart" / filename

    @property
    def path(self) -> Path:
        """Location of the autostart entry."""
        return self._path

    def is_enabled(self) -> bool:
        """Return whether the autostart entry exists."""
        return self._path.is_file()

    def set_enabled(self, enabled: bool) -> bool:
        """Create or remove the autostart entry."""
        if not enabled:
            try:
                self._path.unlink(missing_ok=True)
            except OSError:
                logger.warning("Could not remove the autostart entry", exc_info=True)
                return False
            return True

        contents = (
            "[Desktop Entry]\n"
            "Type=Application\n"
            f"Name={APP_NAME}\n"
            "Comment=Reminds you when to plug in or unplug the charger\n"
            f"Exec={_launch_command()}\n"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
        )
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(contents, encoding="utf-8")
        except OSError:
            logger.warning("Could not write the autostart entry", exc_info=True)
            return False
        return True


def create_startup_service(platform: str | None = None) -> StartupService:
    """Build the startup service appropriate for *platform*.

    Args:
        platform: Override for ``sys.platform``; mainly useful in tests.

    Returns:
        The platform implementation, or :class:`NoopStartupService` when the
        platform is not supported or the platform API is unavailable.
    """
    target = sys.platform if platform is None else platform

    if target.startswith("win"):
        try:
            import winreg  # noqa: F401
        except ImportError:  # pragma: no cover - only on non-Windows runtimes
            return NoopStartupService()
        return WindowsStartupService()

    if target == "darwin":
        return MacOSStartupService()

    if target.startswith(("linux", "freebsd", "openbsd", "netbsd")):
        return LinuxStartupService()

    return NoopStartupService()


__all__ = [
    "LinuxStartupService",
    "MacOSStartupService",
    "NoopStartupService",
    "StartupService",
    "WindowsStartupService",
    "create_startup_service",
]
