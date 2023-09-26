#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:37>

import typing as t
from unittest.mock import patch

import pytest

from retries.retry import AsyncRetry
from retries.stop import IsValueCondition, Sleep, StopAfterAttempt


@pytest.mark.asyncio
async def test_async_does_not_retry_on_matches_value_condition() -> None:
    async def _test(a: int, b: int) -> int:
        return a + b

    retry = AsyncRetry[int](stops=[IsValueCondition(4)])
    result = await retry(_test, a=2, b=2)
    assert result == 4


@pytest.mark.asyncio
async def test_async_retry_raises_on_condition_unmatched() -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](stops=[IsValueCondition(4, max_attempts=2)])

    with pytest.raises(ValueError) as err:
        await retry(_test, 2)


@pytest.mark.asyncio
@pytest.mark.parametrize(("attempts", "expected"), ((1, 1), (2, 2), (3, 3), (10, 10)))
async def test_async_retry_runs_twice_on_stop_after_attempt(
    attempts: int,
    expected: int,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](stops=[StopAfterAttempt(attempts)])

    stop: StopAfterAttempt | None = None
    with pytest.raises(ValueError) as err:
        stop = t.cast(StopAfterAttempt, retry.stops[0])
        assert stop.current_attempt == 0
        await retry(_test, 2)

    assert stop
    assert stop.should_stop is True
    assert stop.current_attempt == expected


@pytest.mark.asyncio
@patch("time.sleep", return_value=None)
@pytest.mark.parametrize(
    ("seconds", "expected"), ((1.0, 1), (3.0, 2), (5.0, 3), (10.0, 10))
)
async def test_async_retry_sleeps_twice_on_sleep_stop(
    patched_time_sleep,
    seconds: float,
    expected: int,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](stops=[Sleep(seconds=seconds, attempts=expected)])

    with pytest.raises(ValueError) as err:
        assert t.cast(Sleep, retry.stops[0]).current_attempt == 0
        await retry(_test, 2)

    stop = t.cast(Sleep, retry.stops[0])

    assert patched_time_sleep.call_count == expected
    assert patched_time_sleep.call_args.args == (seconds,)
    assert stop.should_stop is True
    assert stop.current_attempt == expected


@pytest.mark.asyncio
@patch("time.sleep", return_value=None)
@pytest.mark.parametrize(
    ("seconds", "expected", "attempts"),
    ((1.0, 1, 1), (3.0, 2, 5), (5.0, 3, 5), (10.0, 10, 6)),
)
async def test_async_retry_with_multiple_stops(
    patched_time_sleep,
    seconds: float,
    expected: int,
    attempts: int,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry = AsyncRetry[None](
        stops=[Sleep(seconds=seconds, attempts=expected), StopAfterAttempt(attempts)]
    )

    stop_sleep = t.cast(Sleep, retry.stops[0])
    stop_after_attempt = t.cast(StopAfterAttempt, retry.stops[1])

    with pytest.raises(ValueError):
        assert stop_sleep.current_attempt == 0
        assert stop_after_attempt.current_attempt == 0

        await retry(_test, 2)

    assert patched_time_sleep.call_count == expected
    assert patched_time_sleep.call_args.args == (seconds,)

    assert stop_sleep.should_stop is True
    assert stop_sleep.current_attempt == expected

    assert stop_after_attempt.current_attempt == attempts
    assert stop_after_attempt.should_stop is True
