"""Design-system guard: colour literals may only live in ``colors.py``.

This keeps the "one place for colour" rule enforceable rather than aspirational.
It scans for colour literals inside string literals, which is where they would
appear in a Qt style sheet.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parents[1] / "battery_charge_notifier"
COLORS_MODULE = PACKAGE_ROOT / "colors.py"

#: A hex colour inside a string literal, e.g. ``"#0E1317"``.
HEX_IN_STRING = re.compile(r"""['"]#[0-9a-fA-F]{3,8}['"]""")
#: An explicit rgba()/rgb() colour inside a string literal.
RGB_IN_STRING = re.compile(r"""['"]rgba?\(""")
#: Colour keywords that must go through a token as well.
KEYWORD_IN_STRING = re.compile(r"""['"](?:transparent|black|white|red|green|blue)['"]""")


def python_sources() -> list[Path]:
    """Every Python module in the package except the token module itself."""
    return [
        path
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if path.name != COLORS_MODULE.name
    ]


class TestColourDiscipline:
    def test_package_contains_modules(self) -> None:
        assert len(python_sources()) > 8

    @pytest.mark.parametrize("pattern", [HEX_IN_STRING, RGB_IN_STRING, KEYWORD_IN_STRING])
    def test_no_colour_literals_outside_the_token_module(self, pattern: re.Pattern[str]) -> None:
        offenders: list[str] = []
        for path in python_sources():
            for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
                if pattern.search(line):
                    offenders.append(f"{path.relative_to(PACKAGE_ROOT.parent)}:{number}: {line.strip()}")
        assert offenders == [], "Colour literals must be tokens in colors.py:\n" + "\n".join(offenders)


class TestTokenModule:
    def test_every_token_is_a_string(self) -> None:
        from battery_charge_notifier import colors

        tokens = {
            name: value
            for name, value in vars(colors).items()
            if name.isupper() and not name.startswith("_") and isinstance(value, str)
        }
        assert tokens, "colors.py should define named tokens"
        for name, value in tokens.items():
            assert isinstance(value, str), name
            assert value.strip(), name

    def test_tokens_are_hex_rgba_or_keywords(self) -> None:
        from battery_charge_notifier import colors

        for name, value in vars(colors).items():
            if not name.isupper() or name.startswith("_"):
                continue
            if not isinstance(value, str):
                continue
            assert (
                # Qt accepts #RRGGBB and #AARRGGBB.
                re.fullmatch(r"#[0-9a-fA-F]{6}([0-9a-fA-F]{2})?", value)
                or re.fullmatch(r"rgba\([^)]*\)", value)
                or value == "transparent"
            ), f"{name} = {value!r} is not a valid colour token"

    def test_both_palettes_are_complete(self) -> None:
        from battery_charge_notifier import colors
        from dataclasses import fields

        names = {field.name for field in fields(colors.Palette)}
        assert names == {field.name for field in fields(colors.LIGHT)}
        assert names == {field.name for field in fields(colors.DARK)}

    def test_apply_theme_switches_module_tokens(self) -> None:
        from battery_charge_notifier import colors

        colors.apply_theme("dark")
        assert colors.SURFACE == colors.DARK.SURFACE
        assert colors.ACCENT_PRIMARY == "#60CDFF"
        colors.apply_theme("light")
        assert colors.SURFACE == colors.LIGHT.SURFACE
        assert colors.ACCENT_PRIMARY == "#005FB8"

    def test_action_helpers_cover_both_actions(self) -> None:
        from battery_charge_notifier import colors

        assert colors.accent_for("unplug") == colors.ACCENT_UNPLUG
        assert colors.accent_for("plug_in") == colors.ACCENT_PLUG
        assert colors.accent_dim_for("plug_in") == colors.ACCENT_PLUG_DIM
        assert colors.accent_soft_for("unplug") == colors.ACCENT_UNPLUG_SOFT
