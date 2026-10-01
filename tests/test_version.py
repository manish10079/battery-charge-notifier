"""The published version is a single major.minor.patch string."""

from __future__ import annotations

import re

from battery_charge_notifier import VERSION_INFO, __version__

_SEMVER = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")


def test_version_is_major_minor_patch() -> None:
    assert _SEMVER.fullmatch(__version__)
    assert VERSION_INFO == tuple(int(part) for part in __version__.split("."))
    assert len(VERSION_INFO) == 3
