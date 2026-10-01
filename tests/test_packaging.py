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

from batterylimit import resources

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging" / "batterylimit.spec"
LAUNCHER = ROOT / "packaging" / "launcher.py"
PYPROJECT = ROOT / "pyproject.toml"


class TestFrozenEntryPoint:
    def test_launcher_exists(self) -> None:
        assert LAUNCHER.is_file()

    def test_launcher_uses_an_absolute_import(self) -> None:
        source = LAUNCHER.read_text(encoding="utf-8")
        assert "from batterylimit.main import main" in source
        # A relative import cannot resolve when run as a top-level script.
        assert "from . " not in source
        assert "from .main" not in source

    def test_launcher_is_not_inside_the_package(self) -> None:
        """The entry script must sit outside the package it imports."""
        assert LAUNCHER.parent.name != "batterylimit"

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
        assert "batterylimit" in result.stdout.lower()

    def test_spec_builds_the_launcher_not_the_package_dunder_main(self) -> None:
        spec = SPEC.read_text(encoding="utf-8")
        assert 'ENTRY_POINT = PROJECT_ROOT / "packaging" / "launcher.py"' in spec
        assert "__main__.py" not in spec

    def test_package_dunder_main_still_supports_module_execution(self) -> None:
        """``python -m batterylimit`` must keep working for source installs."""
        result = subprocess.run(
            [sys.executable, "-m", "batterylimit", "--version"],
            capture_output=True,
            text=True,
            cwd=str(ROOT),
            timeout=120,
        )
        assert result.returncode == 0, result.stderr
        assert "batterylimit" in result.stdout.lower()


@pytest.fixture(scope="module")
def spec_text() -> str:
    """The PyInstaller spec file, read once per module."""
    return SPEC.read_text(encoding="utf-8")


class TestSpecContents:
    def test_bundles_the_assets_as_package_data(self, spec_text: str) -> None:
        assert 'datas=[(str(ASSETS), "batterylimit/assets")]' in spec_text

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
        assert package_data["batterylimit"] == ["assets/*"]

    def test_package_discovery_includes_the_subpackages(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        include = config["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "batterylimit*" in include

    def test_console_and_gui_entry_points_are_declared(self) -> None:
        config = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
        assert config["project"]["scripts"]["batterylimit"] == "batterylimit.main:main"
        assert config["project"]["gui-scripts"]["batterylimit-gui"] == "batterylimit.main:main"
