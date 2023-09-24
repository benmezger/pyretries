#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:37>

import typing as t
from unittest.mock import patch

import pytest

from retries.exceptions import RetryConditionError, RetryExaustedError
from retries.retry import AsyncRetry, IsValueCondition, Sleep, StopAfterAttempt


@pytest.fixture
def conditions() -> t.Callable[[int], list[IsValueCondition[int]]]:
    def _conditions(expected: int) -> list[IsValueCondition[int]]:
        return [IsValueCondition(expected)]

    return _conditions


@pytest.mark.asyncio
async def test_async_retry_runs_awaitable(
    conditions: t.Callable[[int], list[IsValueCondition[int]]],
) -> None:
    async def _test(a: int, b: int) -> int:
        return a + b

    retry = AsyncRetry[int](conditions(4), stop=StopAfterAttempt(1))
    result = await retry(_test, a=2, b=2)
    assert result == 4


@pytest.mark.asyncio
async def test_async_retry_raises_on_condition_unmatched(
    conditions: t.Callable[[int], list[IsValueCondition[int]]],
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](conditions(4), stop=StopAfterAttempt(1))
    with pytest.raises(RetryExaustedError):
        await retry(_test, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(("attempts", "expected"), ((1, 1), (2, 2), (3, 3), (10, 10)))
async def test_async_retry_runs_twice_on_stop_after_attempt(
    attempts: int,
    expected: int,
    conditions: t.Callable[[int], list[IsValueCondition[int]]],
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](conditions=conditions(4), stop=StopAfterAttempt(attempts))

    with pytest.raises(RetryExaustedError):
        assert t.cast(StopAfterAttempt, retry.stop).current_attempt == 0
        await retry(_test, 2)

    assert retry.stop.should_stop is True
    assert t.cast(StopAfterAttempt, retry.stop).current_attempt == expected


@pytest.mark.asyncio
@patch("time.sleep", return_value=None)
@pytest.mark.parametrize(
    ("seconds", "expected"), ((1.0, 1), (3.0, 2), (5.0, 3), (10.0, 10))
)
async def test_async_retry_sleeps_twice_on_sleep_stop(
    patched_time_sleep,
    seconds: float,
    expected: int,
    conditions: t.Callable[[int], list[IsValueCondition[int]]],
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](
        conditions=conditions(4), stop=Sleep(seconds=seconds, attempts=expected)
    )

    with pytest.raises(RetryExaustedError):
        assert t.cast(Sleep, retry.stop).current_attempt == 0
        await retry(_test, 2)

    assert patched_time_sleep.call_count == expected
    assert patched_time_sleep.call_args.args == (seconds,)
    assert retry.stop.should_stop is True
    assert t.cast(Sleep, retry.stop).current_attempt == expected
