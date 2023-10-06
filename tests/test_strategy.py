#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-10-06 Fri 20:43>

import random
from unittest.mock import MagicMock

import pytest

from retries import strategy
from retries.exceptions import RetryStrategyExausted


class TestSleepStrategy:
    @pytest.mark.parametrize(("seconds", "attempts"), ((1, 1), (2, 2), (3, 3), (4, 4)))
    def test_sleeps_for_n_seconds(self, seconds: int, attempts: int, sleep: MagicMock):
        s = strategy.Sleep(seconds, attempts)
        assert s.current_attempt == 0

        with pytest.raises(RetryStrategyExausted):
            for _ in range(attempts + 1):
                s.maybe_apply(None)

        sleep.assert_called_with(seconds)
        assert s.current_attempt == attempts

    def test_raises_from_value(self):
        s = strategy.Sleep(1, 0)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(ValueError("Error"))

        assert isinstance(err.value.__cause__, ValueError)

    def test_raises_from_none_when_value_is_not_an_exception(self):
        s = strategy.Sleep(1, 0)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(None)

        assert err.value.__cause__ == None


class TestExponentialBackoffStrategy:
    @pytest.fixture
    def uniform(self, monkeypatch) -> MagicMock:
        monkeypatch.setattr(random, "uniform", mock := MagicMock())
        mock.return_value = 0.6923039770597003
        return mock

    @pytest.mark.parametrize(
        ("base_delay", "attempts", "expected_delays"),
        (
            (1, 1, [2.6923039770597]),
            (2, 2, [4.692303977059701, 8.6923039770597]),
            (3, 3, [6.692303977059701, 12.6923039770597, 24.6923039770597]),
            (
                4,
                4,
                [8.6923039770597, 16.6923039770597, 32.6923039770597, 64.6923039770597],
            ),
        ),
    )
    def test_sleeps_for_n_delay(
        self,
        base_delay: int,
        attempts: int,
        expected_delays: list[float],
        sleep: MagicMock,
        uniform: MagicMock,
    ):
        s = strategy.ExponentialBackoff(attempts, base_delay)
        assert s.current_attempt == 0

        with pytest.raises(RetryStrategyExausted):
            for _ in range(attempts + 1):
                s.maybe_apply(None)

        # checks if sleep was called N types with the calculated delay
        assert [call.args[0] for call in sleep.call_args_list] == expected_delays
        assert s.current_attempt == attempts

    def test_raises_from_value(self):
        s = strategy.ExponentialBackoff(0, 1)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(ValueError("Error"))

        assert isinstance(err.value.__cause__, ValueError)

    def test_raises_from_none_when_value_is_not_an_exception(self):
        s = strategy.ExponentialBackoff(0, 0)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(None)

        assert err.value.__cause__ == None


class TestStopAfterAttempt:
    @pytest.mark.parametrize(("attempts"), (1, 2, 3, 4))
    def test_sleeps_for_n_seconds(self, attempts: int):
        s = strategy.StopAfterAttempt(attempts)
        assert s.current_attempt == 0

        with pytest.raises(RetryStrategyExausted):
            for _ in range(attempts + 1):
                s.maybe_apply(None)

        assert s.current_attempt == attempts

    def test_raises_from_value(self):
        s = strategy.StopAfterAttempt(0)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(ValueError("Error"))

        assert isinstance(err.value.__cause__, ValueError)

    def test_raises_from_none_when_value_is_not_an_exception(self):
        s = strategy.StopAfterAttempt(0)

        with pytest.raises(RetryStrategyExausted) as err:
            s.maybe_apply(None)

        assert err.value.__cause__ == None


class TestWhenReturnValueIs:
    @pytest.mark.parametrize(("attempts",), ((1,), (2,), (3,), (4,)))
    def test_return_value(self, attempts: int):
        s = strategy.StopWhenReturnValue(expected=attempts, max_attempts=2)
        assert s.current_attempt == 0

        assert s.maybe_apply(attempts) is False
        assert s.current_attempt == 1

    def test_raises_when_max_attempts(self):
        s = strategy.StopWhenReturnValue(None, 2)

        with pytest.raises(RetryStrategyExausted) as err:
            for _ in range(3):
                s.maybe_apply(1)

        assert err.value.__cause__ == None


class TestNopStrategy:
    @pytest.mark.parametrize(("attempts",), ((1,), (2,), (3,), (4,)))
    def test_return_value(self, attempts: int):
        s = strategy.NoopStrategy(attempts)
        assert s.current_attempt == 0

        with pytest.raises(RetryStrategyExausted) as err:
            for _ in range(attempts + 1):
                s.maybe_apply(1)

        assert s.current_attempt == attempts
        assert err.value.__cause__ == None
