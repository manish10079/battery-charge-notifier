"""Tests for the single-instance gate."""

from __future__ import annotations

import uuid

import pytest

from batterylimit.single_instance import (
    COMMAND_SHOW_SETTINGS,
    SingleInstance,
    default_server_name,
)


@pytest.fixture
def socket_name() -> str:
    """A socket name unique to each test, so runs never collide."""
    return f"batterylimit-test-{uuid.uuid4().hex}"


@pytest.fixture
def tracked():
    """Track gates so every one is released, even when a test fails."""
    gates: list[SingleInstance] = []

    def make(name: str) -> SingleInstance:
        gate = SingleInstance(name)
        gates.append(gate)
        return gate

    yield make

    for gate in gates:
        gate.release()


class TestAcquisition:
    def test_first_instance_becomes_primary(self, qtbot, socket_name, tracked) -> None:
        gate = tracked(socket_name)
        assert gate.try_acquire() is True
        assert gate.is_primary is True

    def test_second_instance_is_not_primary(self, qtbot, socket_name, tracked) -> None:
        first = tracked(socket_name)
        assert first.try_acquire() is True

        second = tracked(socket_name)
        assert second.try_acquire() is False
        assert second.is_primary is False

    def test_reacquiring_is_idempotent(self, qtbot, socket_name, tracked) -> None:
        gate = tracked(socket_name)
        assert gate.try_acquire() is True
        assert gate.try_acquire() is True

    def test_release_frees_the_lock(self, qtbot, socket_name, tracked) -> None:
        first = tracked(socket_name)
        assert first.try_acquire() is True
        first.release()
        assert first.is_primary is False

        second = tracked(socket_name)
        assert second.try_acquire() is True


class TestHandover:
    def test_second_instance_can_signal_the_first(self, qtbot, socket_name, tracked) -> None:
        first = tracked(socket_name)
        first.try_acquire()

        received: list[str] = []
        first.messageReceived.connect(received.append)

        second = tracked(socket_name)
        assert second.try_acquire() is False
        assert second.notify_running_instance(COMMAND_SHOW_SETTINGS) is True

        qtbot.waitUntil(lambda: received == [COMMAND_SHOW_SETTINGS], timeout=3000)

    def test_notify_without_a_listener_reports_failure(self, qtbot, tracked) -> None:
        gate = tracked(f"batterylimit-absent-{uuid.uuid4().hex}")
        assert gate.notify_running_instance() is False

    def test_default_command_is_open_settings(self, qtbot, socket_name, tracked) -> None:
        first = tracked(socket_name)
        first.try_acquire()

        received: list[str] = []
        first.messageReceived.connect(received.append)

        second = tracked(socket_name)
        second.try_acquire()
        second.notify_running_instance()

        qtbot.waitUntil(lambda: received == [COMMAND_SHOW_SETTINGS], timeout=3000)


class TestNaming:
    def test_server_name_is_per_user(self) -> None:
        name = default_server_name()
        assert name.startswith("batterylimit-")
        assert len(name) > len("batterylimit-")
