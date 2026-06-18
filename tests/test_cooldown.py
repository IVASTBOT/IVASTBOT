import importlib
import sys
import time

import pytest

from ivastbot_hri.core import keys
from ivastbot_hri.core.cooldown import CooldownManager


class FakeClock:
    def __init__(self, current_time=0.0):
        self.current_time = current_time

    def now(self):
        return self.current_time

    def advance(self, seconds):
        self.current_time += seconds


def test_first_execution_is_allowed():
    clock = FakeClock()
    cooldown = CooldownManager(time_provider=clock.now)

    assert cooldown.can_execute(keys.WAVE_HAND)


def test_repeated_execution_before_cooldown_expires_is_blocked():
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=2.0, time_provider=clock.now)

    assert cooldown.try_execute(keys.WAVE_HAND)
    clock.advance(1.0)

    assert not cooldown.can_execute(keys.WAVE_HAND)
    assert not cooldown.try_execute(keys.WAVE_HAND)


def test_execution_after_cooldown_expires_is_allowed():
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=2.0, time_provider=clock.now)

    cooldown.record_execution(keys.WAVE_HAND)
    clock.advance(2.0)

    assert cooldown.can_execute(keys.WAVE_HAND)


def test_different_actions_have_independent_cooldowns():
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=2.0, time_provider=clock.now)

    cooldown.record_execution(keys.WAVE_HAND)

    assert not cooldown.can_execute(keys.WAVE_HAND)
    assert cooldown.can_execute(keys.POINT_LEFT)


def test_per_action_cooldown_overrides_default_cooldown():
    clock = FakeClock()
    cooldown = CooldownManager(
        default_cooldown_seconds=5.0,
        per_action_cooldowns={keys.WAVE_HAND: 1.0},
        time_provider=clock.now,
    )

    cooldown.record_execution(keys.WAVE_HAND)
    clock.advance(1.0)

    assert cooldown.can_execute(keys.WAVE_HAND)


def test_reset_one_action_works():
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=5.0, time_provider=clock.now)

    cooldown.record_execution(keys.WAVE_HAND)
    cooldown.record_execution(keys.POINT_LEFT)
    cooldown.reset(keys.WAVE_HAND)

    assert cooldown.can_execute(keys.WAVE_HAND)
    assert not cooldown.can_execute(keys.POINT_LEFT)


def test_reset_all_actions_works():
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=5.0, time_provider=clock.now)

    cooldown.record_execution(keys.WAVE_HAND)
    cooldown.record_execution(keys.POINT_LEFT)
    cooldown.reset()

    assert cooldown.can_execute(keys.WAVE_HAND)
    assert cooldown.can_execute(keys.POINT_LEFT)


def test_get_remaining_cooldown_returns_expected_value():
    clock = FakeClock(current_time=10.0)
    cooldown = CooldownManager(default_cooldown_seconds=5.0, time_provider=clock.now)

    cooldown.record_execution(keys.WAVE_HAND)
    clock.advance(1.5)

    assert cooldown.get_remaining_cooldown(keys.WAVE_HAND) == pytest.approx(3.5)


def test_cooldown_tests_use_fake_time_provider_without_sleep(monkeypatch):
    clock = FakeClock()
    cooldown = CooldownManager(default_cooldown_seconds=1.0, time_provider=clock.now)

    def fail_sleep(_seconds):
        raise AssertionError("sleep should not be used")

    monkeypatch.setattr(time, "sleep", fail_sleep)
    cooldown.record_execution(keys.WAVE_HAND)
    clock.advance(1.0)

    assert cooldown.can_execute(keys.WAVE_HAND)


def test_cooldown_import_has_no_ros_dependency():
    before = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}

    sys.modules.pop("ivastbot_hri.core.cooldown", None)
    module = importlib.import_module("ivastbot_hri.core.cooldown")

    after = {name for name in sys.modules if name.split(".", maxsplit=1)[0] == "rclpy"}
    assert module.CooldownManager is not None
    assert after == before
