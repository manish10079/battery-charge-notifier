"""Tests for the warning/re-arm state machine.

Every documented transition is exercised explicitly, including the boundary
values of both re-arm points, because the anti-nag behaviour is the single most
important part of the application.
"""

from __future__ import annotations

import pytest

from batterylimit.battery_service import BatteryState
from batterylimit.monitor import (
    ChannelPhase,
    Thresholds,
    WarningKind,
    WarningStateMachine,
)


def make_state(percent: int, plugged: bool, present: bool = True) -> BatteryState:
    """Build a synthetic battery state."""
    return BatteryState(
        percent=percent,
        plugged=plugged,
        charging=plugged and percent < 100,
        present=present,
    )


@pytest.fixture
def machine() -> WarningStateMachine:
    """A machine with the documented defaults: upper 80, lower 20, gap 5."""
    return WarningStateMachine(Thresholds(upper_limit=80, lower_limit=20, rearm_gap=5))


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
class TestThresholds:
    def test_rearm_points_are_derived_from_the_gap(self) -> None:
        limits = Thresholds(upper_limit=80, lower_limit=20, rearm_gap=5)
        assert limits.upper_rearm_point == 75
        assert limits.lower_rearm_point == 25

    def test_thresholds_come_from_config(self, default_config) -> None:
        limits = Thresholds.from_config(default_config)
        assert limits.upper_limit == 80
        assert limits.lower_limit == 20
        assert limits.snooze_seconds == 15 * 60


# ---------------------------------------------------------------------------
# Upper warning
# ---------------------------------------------------------------------------
class TestUpperWarning:
    def test_fires_when_plugged_at_the_limit(self, machine: WarningStateMachine) -> None:
        event = machine.update(make_state(80, plugged=True), now=0.0)
        assert event is not None
        assert event.kind is WarningKind.UPPER
        assert event.percent == 80
        assert event.action == "unplug"
        assert event.message == "Battery at 80% \u2014 unplug the charger."

    def test_fires_when_plugged_above_the_limit(self, machine: WarningStateMachine) -> None:
        event = machine.update(make_state(97, plugged=True), now=0.0)
        assert event is not None
        assert event.percent == 97

    def test_does_not_fire_on_battery_power(self, machine: WarningStateMachine) -> None:
        """Never tell the user to unplug a charger that is not connected."""
        assert machine.update(make_state(95, plugged=False), now=0.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED

    def test_does_not_fire_below_the_limit(self, machine: WarningStateMachine) -> None:
        assert machine.update(make_state(79, plugged=True), now=0.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED

    def test_fires_only_once_while_still_plugged(self, machine: WarningStateMachine) -> None:
        """The core anti-nag guarantee: one warning, then quiet."""
        assert machine.update(make_state(85, plugged=True), now=0.0) is not None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.QUIET
        for tick in range(1, 20):
            assert machine.update(make_state(85, plugged=True), now=float(tick)) is None

    def test_stays_latched_at_the_rearm_boundary(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        # 75 == upper - gap, which is NOT below the re-arm point.
        assert machine.update(make_state(75, plugged=True), now=1.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.QUIET

    def test_rearms_below_the_rearm_point(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        assert machine.update(make_state(74, plugged=True), now=1.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED

    def test_refires_after_rearming(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.update(make_state(74, plugged=True), now=1.0)
        event = machine.update(make_state(86, plugged=True), now=2.0)
        assert event is not None
        assert event.percent == 86

    def test_rearms_when_unplugged_then_refires_on_replug(
        self, machine: WarningStateMachine
    ) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        # Unplugging drops below the re-arm point, so the channel re-arms.
        machine.update(make_state(70, plugged=False), now=1.0)
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED
        assert machine.update(make_state(85, plugged=True), now=2.0) is not None


# ---------------------------------------------------------------------------
# Lower warning
# ---------------------------------------------------------------------------
class TestLowerWarning:
    def test_fires_when_on_battery_at_the_limit(self, machine: WarningStateMachine) -> None:
        event = machine.update(make_state(20, plugged=False), now=0.0)
        assert event is not None
        assert event.kind is WarningKind.LOWER
        assert event.action == "plug_in"
        assert event.message == "Battery at 20% \u2014 plug in the charger."

    def test_does_not_fire_while_plugged(self, machine: WarningStateMachine) -> None:
        """Never tell the user to plug in a charger that is already connected."""
        assert machine.update(make_state(5, plugged=True), now=0.0) is None
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.ARMED

    def test_does_not_fire_above_the_limit(self, machine: WarningStateMachine) -> None:
        assert machine.update(make_state(21, plugged=False), now=0.0) is None

    def test_fires_only_once_while_still_low(self, machine: WarningStateMachine) -> None:
        assert machine.update(make_state(15, plugged=False), now=0.0) is not None
        for tick in range(1, 20):
            assert machine.update(make_state(15, plugged=False), now=float(tick)) is None
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.QUIET

    def test_stays_latched_at_the_rearm_boundary(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(15, plugged=False), now=0.0)
        # 25 == lower + gap, which is NOT above the re-arm point.
        machine.update(make_state(25, plugged=False), now=1.0)
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.QUIET

    def test_rearms_above_the_rearm_point(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(15, plugged=False), now=0.0)
        machine.update(make_state(26, plugged=False), now=1.0)
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.ARMED

    def test_does_not_refire_merely_because_it_was_replugged(
        self, machine: WarningStateMachine
    ) -> None:
        """Plugging in silences the warning but does not re-arm it."""
        machine.update(make_state(15, plugged=False), now=0.0)
        machine.update(make_state(16, plugged=True), now=1.0)
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.QUIET
        assert machine.update(make_state(16, plugged=False), now=2.0) is None

    def test_refires_after_a_full_charge_cycle(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(15, plugged=False), now=0.0)
        machine.update(make_state(80, plugged=True), now=1.0)
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.ARMED
        assert machine.update(make_state(10, plugged=False), now=2.0) is not None


# ---------------------------------------------------------------------------
# Snooze
# ---------------------------------------------------------------------------
class TestSnooze:
    def test_snooze_suppresses_then_reminds(self, machine: WarningStateMachine) -> None:
        assert machine.update(make_state(85, plugged=True), now=0.0) is not None
        machine.snooze(WarningKind.UPPER, now=0.0)
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.SNOOZED
        assert machine.is_snoozed(WarningKind.UPPER, now=100.0)

        # Still muted well before the deadline.
        assert machine.update(make_state(85, plugged=True), now=600.0) is None
        # Past the deadline, still actionable: remind the user once more.
        event = machine.update(make_state(85, plugged=True), now=901.0)
        assert event is not None
        assert event.kind is WarningKind.UPPER

    def test_snooze_does_not_refire_twice_after_expiry(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.snooze(WarningKind.UPPER, now=0.0)
        assert machine.update(make_state(85, plugged=True), now=901.0) is not None
        assert machine.update(make_state(85, plugged=True), now=902.0) is None

    def test_snooze_expires_when_the_battery_recovers(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.snooze(WarningKind.UPPER, now=0.0)
        # Drops below the re-arm point while snoozed: still muted, but the
        # channel is re-armed as soon as the snooze window closes.
        assert machine.update(make_state(70, plugged=False), now=100.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.SNOOZED
        assert machine.update(make_state(70, plugged=False), now=1000.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED

    def test_snooze_is_not_cancelled_by_an_unrelated_recovery(
        self, machine: WarningStateMachine
    ) -> None:
        """A snooze must run its full course even though the other channel's
        re-arm condition is trivially satisfied."""
        machine.snooze_all(now=0.0)
        assert machine.update(make_state(95, plugged=True), now=1.0) is None
        assert machine.update(make_state(10, plugged=False), now=2.0) is None
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.SNOOZED
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.SNOOZED

    def test_snooze_only_affects_the_chosen_channel(self, machine: WarningStateMachine) -> None:
        machine.snooze(WarningKind.UPPER, now=0.0)
        event = machine.update(make_state(10, plugged=False), now=1.0)
        assert event is not None
        assert event.kind is WarningKind.LOWER

    def test_snooze_all_mutes_both(self, machine: WarningStateMachine) -> None:
        machine.snooze_all(now=0.0)
        assert machine.update(make_state(85, plugged=True), now=1.0) is None
        assert machine.update(make_state(10, plugged=False), now=2.0) is None

    def test_reset_rearms_everything(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.snooze_all(now=0.0)
        machine.reset()
        assert machine.phase(WarningKind.UPPER) is ChannelPhase.ARMED
        assert machine.phase(WarningKind.LOWER) is ChannelPhase.ARMED
        assert machine.update(make_state(85, plugged=True), now=1.0) is not None


# ---------------------------------------------------------------------------
# Cross-cutting behaviour
# ---------------------------------------------------------------------------
class TestGeneralBehaviour:
    def test_absent_battery_never_warns(self, machine: WarningStateMachine) -> None:
        assert machine.update(BatteryState.absent(), now=0.0) is None

    def test_only_one_event_per_update(self, machine: WarningStateMachine) -> None:
        """Upper and lower are mutually exclusive by construction."""
        assert machine.update(make_state(85, plugged=True), now=0.0) is not None
        assert machine.update(make_state(85, plugged=True), now=1.0) is None

    def test_applying_thresholds_does_not_re_fire_a_latched_warning(
        self, machine: WarningStateMachine
    ) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.apply_thresholds(Thresholds(upper_limit=60, lower_limit=20, rearm_gap=5))
        assert machine.update(make_state(85, plugged=True), now=1.0) is None

    def test_new_threshold_applies_to_the_next_cycle(self, machine: WarningStateMachine) -> None:
        machine.update(make_state(85, plugged=True), now=0.0)
        machine.apply_thresholds(Thresholds(upper_limit=90, lower_limit=20, rearm_gap=5))
        machine.update(make_state(50, plugged=True), now=1.0)  # re-arms
        assert machine.update(make_state(85, plugged=True), now=2.0) is None
        assert machine.update(make_state(95, plugged=True), now=3.0) is not None

    def test_full_charge_then_drain_cycle(self, machine: WarningStateMachine) -> None:
        """A realistic scripted session warns on each crossing, and only once."""
        script = [
            (30, True), (81, True), (85, True), (85, True),
            (79, True), (74, True),
            (40, False), (21, False), (19, False), (19, False),
            (26, False), (60, True), (90, True),
        ]
        events = [
            event
            for tick, (percent, plugged) in enumerate(script)
            if (event := machine.update(make_state(percent, plugged), now=float(tick)))
        ]
        assert [event.kind for event in events] == [
            WarningKind.UPPER,  # 81% while plugged
            WarningKind.LOWER,  # 19% on battery power
            WarningKind.UPPER,  # 90% after re-arming and re-charging
        ]
        assert [event.percent for event in events] == [81, 19, 90]
