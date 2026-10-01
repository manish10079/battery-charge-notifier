"""Contract tests for the packaging configuration.

The frozen build has a specific requirement that is easy to break and invisible
until someone runs the executable: PyInstaller executes its entry script as a
top-level module named ``__main__``, which has no parent package. An entry point
that lives *inside* the package and uses a relative import therefore crashes with
"attempted relative import with no known parent package" - the build still
succeeds, and the result is a broken executable.

These tests pin that contract down without running a full build.
"""

from __future__ import annotations

import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

from battery_charge_notifier import resources

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "battery_charge_notifier.spec"
LAUNCHER = ROOT / "packaging" / "launcher.py"
PYPROJECT = ROOT / "pyproject.toml"


class TestFrozenEntryPoint:
    def test_launcher_exists(self) -> None:
        assert LAUNCHER.is_file()

    def test_launcher_uses_an_absolute_import(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")
        assert "from battery_charge_notifier.main import main" in source
        # A relative import cannot resolve when run as a top-level script.
        assert "from . " not in source
        assert "from .main" not in source

    def test_launcher_is_not_inside_the_package(self) -> None:
        """The entry script must sit outside the package it imports."""
        assert LAUNCHER.parent.name != "battery_charge_notifier"

    def test_launcher_runs_as_a_top_level_script(self) -> None:
        """Simulates exactly how PyInstaller invokes the entry point."""
        result = subprocess.run(
            [sys.executable, str(LAUNCHER), "--version"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "battery-charge-notifier" in result.stdout.lower()

    def test_spec_builds_the_launcher_not_the_package_dunder_main(self) -> None:
        spec = SPEC.read_text(encoding="utf-8")
        assert 'ENTRY_POINT = PROJECT_ROOT / "packaging" / "launcher.py"' in spec
        assert "__main__.py" not in spec

    def test_package_dunder_main_still_supports_module_execution(self) -> None:
        """``python -m battery_charge_notifier`` must keep working for source installs."""
        result = subprocess.run(
            [sys.executable, "-m", "battery_charge_notifier", "--version"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "battery-charge-notifier" in result.stdout.lower()


@pytest.fixture(scope="module")
def spec_text() -> str:
    """The PyInstaller spec file, read once per module."""
    return SPEC.read_text(encoding="utf-8")


class TestSpecContents:
    def test_bundles_the_assets_as_package_data(self, spec_text: str) -> None:
        assert 'datas=[(str(ASSETS), "battery_charge_notifier/assets")]' in spec_text

    def test_produces_a_single_file(self, spec_text: str) -> None:
        # A spec that produces a single file has no COLLECT step.
        assert "COLLECT(" not in spec_text
        assert "EXE(" in spec_text

    def test_builds_a_windowed_executable(self, spec_text: str) -> None:
        assert "console=False" in spec_text

    def test_uses_the_application_icon(self, spec_text: str) -> None:
        assert 'icon=str(ASSETS / "app.ico")' in spec_text

    def test_excludes_development_only_packages(self, spec_text: str) -> None:
        for package in ("pytest", "PyInstaller", "tkinter"):
            assert f'"{package}"' in spec_text


class TestBundlePruning:
    """The release build deliberately drops Qt subsystems the app never loads.

    PyInstaller cannot be asked to leave them out through ``excludes`` alone -
    the PySide6 hook collects the libraries as binaries - so the spec filters
    ``Analysis.binaries``. These tests pin down both halves of the contract: the
    heavy unused subsystems stay excluded, and the plugins and settings that are
    genuinely required stay in.
    """

    HEAVY_UNUSED = (
        "opengl32sw.dll",
        "Qt6Qml.dll",
        "Qt6Quick.dll",
        "Qt6Pdf.dll",
        "Qt6Svg.dll",
        "libcrypto-3.dll",
        "libssl-3.dll",
    )

    def test_heavy_unused_subsystems_are_pruned(self, spec_text: str) -> None:
        for library in self.HEAVY_UNUSED:
            assert f'"{library}"' in spec_text, f"{library} is no longer pruned"

    def test_required_plugins_are_retained(self, spec_text: str) -> None:
        # The .ico window icon needs the ICO image format, and Qt cannot start
        # without a platform plugin.
        assert '"qico.dll"' in spec_text
        assert '"qwindows.dll"' in spec_text

    def test_binaries_are_filtered(self, spec_text: str) -> None:
        assert "a.binaries = prune_qt(a.binaries)" in spec_text

    def test_openssl_dependants_are_excluded_with_it(self, spec_text: str) -> None:
        """Pruning a DLL without pruning its dependants leaves a broken bundle.

        CPython's ``_ssl`` and ``_hashlib`` extensions link against libcrypto and
        libssl. Removing the libraries while those modules remain would produce an
        executable that fails at import time, so they must be excluded together.
        """
        for module in ("ssl", "_ssl", "_hashlib"):
            assert f'"{module}"' in spec_text, f"{module} must be excluded with OpenSSL"


class TestBundledAssets:
    @pytest.mark.parametrize(
        "name",
        [
            resources.APP_ICON,
            resources.APP_ICON_PNG,
            resources.TRAY_OK,
            resources.TRAY_PLUG,
            resources.TRAY_UNPLUG,
            resources.TRAY_PAUSED,
            resources.ARROW_UP,
            resources.ARROW_DOWN,
        ],
    )
    def test_asset_is_present_and_loadable(self, name: str) -> None:
        assert resources.has_asset(name), f"{name} is missing; run tools/generate_assets.py"
        assert resources.asset_path(name).stat().st_size > 0

    def test_assets_are_shipped_as_package_data(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        package_data = config["tool"]["setuptools"]["package-data"]
        assert package_data["battery_charge_notifier"] == ["assets/*"]

    def test_package_discovery_includes_the_subpackages(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        include = config["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "battery_charge_notifier*" in include

    def test_console_and_gui_entry_points_are_declared(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        console = config["project"]["scripts"]
        gui = config["project"]["gui-scripts"]
        # The distribution and command names are kebab-case; only the importable
        # package uses snake_case.
        assert console["battery-charge-notifier"] == "battery_charge_notifier.main:main"
        assert gui["battery-charge-notifier-gui"] == "battery_charge_notifier.main:main"

    def test_distribution_name_is_kebab_case(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        assert config["project"]["name"] == "battery-charge-notifier"
