#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:37>

import typing as t
from unittest.mock import patch

import pytest

from retries.exceptions import RetryExaustedError
from retries.retry import AsyncRetry, Retry, retry
from retries.strategy import Sleep, StopAfterAttempt, StopWhenReturnValue

AsyncRetrySleepFixtureT = t.Callable[..., tuple[AsyncRetry[t.Awaitable[None]], Sleep]]
RetrySleepFixtureT = t.Callable[..., tuple[Retry[None], Sleep]]


@pytest.fixture
def async_retry_sleep() -> AsyncRetrySleepFixtureT:
    def _retry_sleep(seconds: int = 1, attempts: int = 3) -> tuple[AsyncRetry, Sleep]:
        return (
            AsyncRetry[t.Awaitable[None]](
                strategies=[stop_sleep := Sleep(seconds=seconds, attempts=attempts)],
                on_exceptions=[ValueError],
            ),
            stop_sleep,
        )

    return _retry_sleep


@pytest.fixture
def retry_sleep() -> RetrySleepFixtureT:
    def _retry_sleep(seconds: int = 1, attempts: int = 3) -> tuple[Retry, Sleep]:
        return (
            Retry[None](
                strategies=[stop_sleep := Sleep(seconds=seconds, attempts=attempts)],
                on_exceptions=[ValueError],
            ),
            stop_sleep,
        )

    return _retry_sleep


@pytest.mark.asyncio
async def test_async_does_not_retry_on_matches_value_condition() -> None:
    async def _test(a: int, b: int) -> int:
        return a + b

    # TODO: Refactor test to use retry_fixture instead.
    # This also removes the needs to the type cast + indexes
    retry = AsyncRetry[t.Awaitable[int]](strategies=[StopWhenReturnValue(4)])
    result = await retry(_test, a=2, b=2)
    assert result == 4


@pytest.mark.asyncio
async def test_async_retry_raises_on_condition_unmatched() -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    # TODO: Refactor test to use retry_fixture instead.
    # This also removes the needs to the type cast + indexes
    retry = AsyncRetry[t.Awaitable[None]](
        strategies=[StopWhenReturnValue(4, max_attempts=2)]
    )

    with pytest.raises(RetryExaustedError) as err:
        await retry(_test, 2)

    assert isinstance(err.value.__cause__, ValueError)


@pytest.mark.asyncio
@pytest.mark.parametrize(("attempts", "expected"), ((1, 1), (2, 2), (3, 3), (10, 10)))
async def test_async_retry_runs_twice_on_stop_after_attempt(
    attempts: int,
    expected: int,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    # TODO: Refactor test to use retry_fixture instead.
    # This also removes the needs to the type cast + indexes
    retry = AsyncRetry[t.Awaitable[None]](strategies=[StopAfterAttempt(attempts)])

    stop: StopAfterAttempt | None = None
    with pytest.raises(RetryExaustedError) as err:
        stop = t.cast(StopAfterAttempt, retry.strategies[0])
        assert stop.current_attempt == 0
        await retry(_test, 2)

    assert isinstance(err.value.__cause__, ValueError)
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
    async_retry_sleep: AsyncRetrySleepFixtureT,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry, sleep = async_retry_sleep(seconds=seconds, attempts=expected)

    with pytest.raises(RetryExaustedError) as err:
        assert sleep.current_attempt == 0
        await retry(_test, 2)

    assert isinstance(err.value.__cause__, ValueError)
    assert patched_time_sleep.call_count == expected
    assert patched_time_sleep.call_args.args == (seconds,)


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
    async_retry_sleep: AsyncRetrySleepFixtureT,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry, sleep = async_retry_sleep(seconds=seconds, attempts=expected)
    retry.strategies.append(after_attempt := StopAfterAttempt(attempts))

    with pytest.raises(RetryExaustedError) as err:
        assert sleep.current_attempt == 0
        assert after_attempt.current_attempt == 0

        await retry(_test, 2)

    assert isinstance(err.value.__cause__, ValueError)
    assert patched_time_sleep.call_count == expected
    assert patched_time_sleep.call_args.args == (seconds,)

    assert sleep.should_stop is True
    assert sleep.current_attempt == expected

    assert after_attempt.current_attempt == attempts
    assert after_attempt.should_stop is True


@pytest.mark.asyncio
async def test_raises_exception_when_not_in_exception_list(
    async_retry_sleep: AsyncRetrySleepFixtureT,
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry, sleep = async_retry_sleep()
    retry.on_exceptions = set((KeyError,))

    with pytest.raises(RetryExaustedError) as err:
        await retry(_test, 2)

        assert sleep.current_attempt == 0

    assert isinstance(err.value.__cause__, ValueError)


@pytest.mark.asyncio
@patch("time.sleep", return_value=None)
async def test_raises_applies_strategies_when_in_exception_list(
    patched_time_sleep, async_retry_sleep: AsyncRetrySleepFixtureT
) -> None:
    async def _test(_: int) -> None:
        raise ValueError("Something is wrong")

    retry, sleep = async_retry_sleep()
    retry.on_exceptions = set((ValueError,))

    with pytest.raises(RetryExaustedError) as err:
        assert sleep.current_attempt == 0
        await retry(_test, 2)

    assert patched_time_sleep.call_count == 3
    assert patched_time_sleep.call_args.args == (1,)
    assert isinstance(err.value.__cause__, ValueError)
    assert sleep.current_attempt == 3


@pytest.mark.asyncio
@patch("time.sleep", return_value=None)
async def test_retry_decorator_async(
    patched_time_sleep, async_retry_sleep: AsyncRetrySleepFixtureT
) -> None:
    async def _test() -> None:
        raise ValueError("Something is wrong")

    _, sleep = async_retry_sleep()

    with pytest.raises(RetryExaustedError) as err:
        await retry(strategies=[sleep])(_test)()

    assert patched_time_sleep.call_count == 3
    assert patched_time_sleep.call_args.args == (1,)
    assert sleep.attempts == 3
    assert isinstance(err.value.__cause__, ValueError)


@patch("time.sleep", return_value=None)
def test_retry_decorator_sync(
    patched_time_sleep, retry_sleep: RetrySleepFixtureT
) -> None:
    def _test() -> None:
        raise ValueError("Something is wrong")

    _, sleep = retry_sleep()

    with pytest.raises(RetryExaustedError) as err:
        retry(strategies=[sleep])(_test)()

    assert patched_time_sleep.call_count == 3
    assert patched_time_sleep.call_args.args == (1,)
    assert sleep.attempts == 3
    assert isinstance(err.value.__cause__, ValueError)


def test_does_not_retry_on_matches_value_condition(
    retry_sleep: RetrySleepFixtureT,
) -> None:
    def _test() -> int:
        return 2

    retry, _ = retry_sleep()
    result = t.cast(Retry[int], retry)(_test)
    assert result == 2
