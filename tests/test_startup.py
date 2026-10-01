"""Tests for the per-platform launch-at-login services.

The Windows service is exercised against an in-memory stand-in for the
``winreg`` module, so the suite never writes to the machine's ``Run`` key. The
macOS and Linux services write into ``tmp_path``.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

from batterylimit import startup
from batterylimit.startup import (
    LinuxStartupService,
    MacOSStartupService,
    NoopStartupService,
    WindowsStartupService,
    create_startup_service,
)

RUN_KEY = startup.WINDOWS_RUN_KEY


class _FakeKey:
    """Context-manager stand-in for a registry handle."""

    def __init__(self, path: str) -> None:
        self.path = path

    def __enter__(self) -> _FakeKey:
        return self

    def __exit__(self, *exc_info: object) -> bool:
        return False


class FakeWinreg(types.ModuleType):
    """A tiny in-memory ``winreg`` implementing only what the service uses."""

    HKEY_CURRENT_USER = "HKCU"
    KEY_SET_VALUE = 0x0002
    REG_SZ = 1

    def __init__(self) -> None:
        super().__init__("winreg")
        self.values: dict[tuple[str, str], str] = {}
        self.keys: set[str] = set()
        self.hives: set[str] = set()

    def CreateKeyEx(self, hive, path, reserved=0, access=0) -> _FakeKey:  # noqa: N802
        self.keys.add(path)
        self.hives.add(hive)
        return _FakeKey(path)

    def OpenKey(self, hive, path, reserved=0, access=0) -> _FakeKey:  # noqa: N802
        self.hives.add(hive)
        if path not in self.keys:
            raise FileNotFoundError(path)
        return _FakeKey(path)

    def SetValueEx(self, key: _FakeKey, name, reserved, kind, value) -> None:  # noqa: N802
        self.values[(key.path, name)] = value

    def QueryValueEx(self, key: _FakeKey, name):  # noqa: N802
        try:
            return self.values[(key.path, name)], self.REG_SZ
        except KeyError:
            raise FileNotFoundError(name) from None

    def DeleteValue(self, key: _FakeKey, name) -> None:  # noqa: N802
        try:
            del self.values[(key.path, name)]
        except KeyError:
            raise FileNotFoundError(name) from None


@pytest.fixture
def fake_winreg(monkeypatch) -> FakeWinreg:
    """Install an in-memory ``winreg`` and return it."""
    fake = FakeWinreg()
    monkeypatch.setitem(sys.modules, "winreg", fake)
    return fake


class TestWindowsStartupService:
    def test_disabled_when_the_value_is_absent(self, fake_winreg: FakeWinreg) -> None:
        assert WindowsStartupService().is_enabled() is False

    def test_enabling_writes_the_run_value(self, fake_winreg: FakeWinreg) -> None:
        service = WindowsStartupService()
        assert service.set_enabled(True) is True
        assert service.is_enabled() is True
        assert (RUN_KEY, startup.WINDOWS_VALUE_NAME) in fake_winreg.values

    def test_command_invokes_the_module(self, fake_winreg: FakeWinreg) -> None:
        WindowsStartupService().set_enabled(True)
        command = fake_winreg.values[(RUN_KEY, startup.WINDOWS_VALUE_NAME)]
        assert "batterylimit" in command
        assert sys.executable in command

    def test_disabling_removes_the_value(self, fake_winreg: FakeWinreg) -> None:
        service = WindowsStartupService()
        service.set_enabled(True)
        assert service.set_enabled(False) is True
        assert service.is_enabled() is False

    def test_disabling_twice_is_harmless(self, fake_winreg: FakeWinreg) -> None:
        service = WindowsStartupService()
        assert service.set_enabled(False) is True

    def test_only_touches_hkcu(self, fake_winreg: FakeWinreg) -> None:
        """Per-user registration must never need administrator rights."""
        source = Path(startup.__file__).read_text(encoding="utf-8")
        assert "HKEY_LOCAL_MACHINE" not in source
        WindowsStartupService().set_enabled(True)
        assert fake_winreg.hives == {"HKCU"}


class TestMacOSStartupService:
    def test_writes_a_launch_agent(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        service = MacOSStartupService()
        assert service.is_enabled() is False

        assert service.set_enabled(True) is True
        assert service.path.is_file()
        assert service.path.parent.name == "LaunchAgents"
        assert b"com.batterylimit" in service.path.read_bytes()

    def test_plist_contains_absolute_paths(self, tmp_path: Path, monkeypatch) -> None:
        import plistlib

        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        service = MacOSStartupService()
        service.set_enabled(True)

        payload = plistlib.loads(service.path.read_bytes())
        assert payload["RunAtLoad"] is True
        assert Path(payload["ProgramArguments"][0]).is_absolute()

    def test_disabling_removes_the_agent(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setattr(Path, "home", classmethod(lambda cls: tmp_path))
        service = MacOSStartupService()
        service.set_enabled(True)
        assert service.set_enabled(False) is True
        assert not service.path.exists()


class TestLinuxStartupService:
    def test_writes_an_autostart_entry(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        service = LinuxStartupService()
        assert service.is_enabled() is False

        assert service.set_enabled(True) is True
        assert service.path == tmp_path / "autostart" / "batterylimit.desktop"

        contents = service.path.read_text(encoding="utf-8")
        assert contents.startswith("[Desktop Entry]")
        assert "Type=Application" in contents
        assert "Exec=" in contents

    def test_disabling_removes_the_entry(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        service = LinuxStartupService()
        service.set_enabled(True)
        assert service.set_enabled(False) is True
        assert not service.path.exists()


class TestFactory:
    def test_windows(self) -> None:
        assert isinstance(create_startup_service("win32"), WindowsStartupService)

    def test_macos(self) -> None:
        assert isinstance(create_startup_service("darwin"), MacOSStartupService)

    @pytest.mark.parametrize("platform", ["linux", "freebsd", "openbsd"])
    def test_unix(self, platform: str) -> None:
        assert isinstance(create_startup_service(platform), LinuxStartupService)

    def test_unknown_platform_falls_back_to_noop(self) -> None:
        assert isinstance(create_startup_service("emx"), NoopStartupService)

    def test_noop_never_claims_support(self) -> None:
        service = NoopStartupService()
        assert service.is_enabled() is False
        assert service.set_enabled(True) is False
        assert service.is_enabled() is False
