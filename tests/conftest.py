"""Test-suite shared fixtures."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

# Allow ``pytest`` to be run without an editable install by making the project
# root importable.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from battery_charge_notifier.app_config import AppConfig  # noqa: E402
from battery_charge_notifier.battery_service import BatteryState  # noqa: E402


class StubBatteryService:
    """A :class:`BatteryService` that replays scripted states then holds the last.

    Attributes:
        states: The script of states to hand out, one per call.
        calls: Number of times :meth:`read` has been called.
    """

    def __init__(self, states: list[BatteryState] | BatteryState) -> None:
        self.states = states if isinstance(states, list) else [states]
        self.calls = 0

    def read(self) -> BatteryState:
        """Return the next scripted state, repeating the final one forever."""
        index = min(self.calls, len(self.states) - 1)
        self.calls += 1
        return self.states[index]


@pytest.fixture
def default_config() -> AppConfig:
    """Factory-default configuration (upper 80, lower 20)."""
    return AppConfig()
