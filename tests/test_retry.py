#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:37>

import typing as t
from unittest.mock import AsyncMock, MagicMock

import pytest

from retries.exceptions import RetryExaustedError
from retries.retry import (
    AfterHookFuncT,
    AsyncRetry,
    BaseRetry,
    BeforeHookFuncT,
    Retry,
    retry,
)
from retries.strategy import NoopStrategy, Strategy


@pytest.fixture
def async_retry():
    def _async_retry(
        strategies: list[Strategy[t.Any]] | None = None,
        on_exceptions: list[type[Exception]] | None = None,
        before_hooks: list[BeforeHookFuncT] | None = None,
        after_hooks: list[AfterHookFuncT] | None = None,
    ) -> AsyncRetry[t.Any]:
        return AsyncRetry[t.Any](
            strategies=strategies or [],
            on_exceptions=on_exceptions,
            before_hooks=before_hooks or [],
            after_hooks=after_hooks or [],
        )

    return _async_retry


@pytest.fixture
def sync_retry():
    def _sync_retry(
        strategies: list[Strategy[t.Any]] | None = None,
        on_exceptions: list[type[Exception]] | None = None,
        before_hooks: list[BeforeHookFuncT] | None = None,
        after_hooks: list[AfterHookFuncT] | None = None,
    ) -> Retry[t.Any]:
        return Retry[t.Any](
            strategies=strategies or [],
            on_exceptions=on_exceptions,
            before_hooks=before_hooks or [],
            after_hooks=after_hooks or [],
        )

    return _sync_retry


@pytest.fixture
def func() -> MagicMock:
    func_mock = MagicMock()
    func_mock.__name__ = "func_mock"
    return func_mock


@pytest.fixture
def async_func() -> AsyncMock:
    async_func_mock = AsyncMock()
    async_func_mock.__name__ = "async_func_mock"
    return async_func_mock


@pytest.mark.asyncio
async def test_async_retry_runs_func(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.return_value = 4

    retry = async_retry()
    result = await retry(async_func)

    assert result == 4
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_retry_runs_func_with_args(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.return_value = 4

    retry = async_retry()
    kwargs = dict(a=2, b=2)
    result = await retry(async_func, **kwargs)

    assert result == 4
    assert async_func.call_count == 1
    assert async_func.call_args.kwargs == kwargs


@pytest.mark.asyncio
async def test_async_retry_raises_exception(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.side_effect = ValueError

    retry = async_retry()
    with pytest.raises(RetryExaustedError) as err:
        await retry(async_func)

    assert isinstance(err.value.__cause__, ValueError)
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_raises_exception_on_unmapped_exception(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: MagicMock
) -> None:
    async_func.side_effect = KeyError

    retry = async_retry(on_exceptions=[ValueError])
    with pytest.raises(RetryExaustedError) as err:
        await retry(async_func)

    assert isinstance(err.value.__cause__, KeyError)
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_applies_before_hook(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    hook_mock = MagicMock()

    retry = async_retry(
        on_exceptions=[KeyError],
        before_hooks=[hook_mock],
    )

    await retry(async_func)
    assert hook_mock.call_count == 1
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_applies_list_of_before_hooks(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    hooks = []

    for _ in range(5):
        hooks.append(MagicMock())

    retry = async_retry(
        on_exceptions=[KeyError],
        before_hooks=hooks,
    )

    await retry(async_func)

    for hook in hooks:
        assert hook.call_count == 1
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_applies_after_hook(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    hook_mock = MagicMock()

    retry = async_retry(
        on_exceptions=[KeyError],
        after_hooks=[hook_mock],
    )

    await retry(async_func)
    assert hook_mock.call_count == 1
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_applies_list_of_after_hooks(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.return_value = 1

    hooks = []
    for _ in range(5):
        hooks.append(MagicMock())

    retry = async_retry(
        on_exceptions=[KeyError],
        after_hooks=hooks,
    )

    await retry(async_func)

    for hook in hooks:
        assert hook.call_count == 1
    assert async_func.call_count == 1


@pytest.mark.asyncio
async def test_async_applies_strategy(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.side_effect = KeyError

    retry = async_retry(
        strategies=[noop := NoopStrategy(2)],
    )

    with pytest.raises(RetryExaustedError) as err:
        await retry(async_func)
    assert isinstance(err.value.__cause__, KeyError)
    assert async_func.call_count == 3
    assert noop.current_attempt == 2


@pytest.mark.asyncio
async def test_async_applies_strategy_and_raises(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.side_effect = KeyError

    retry = async_retry(
        strategies=[NoopStrategy(0)],
    )

    with pytest.raises(RetryExaustedError):
        await retry(async_func)


@pytest.mark.asyncio
async def test_async_applies_multiple_strategies(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.side_effect = KeyError

    retry = async_retry(
        strategies=[noop := NoopStrategy(2), noop_2 := NoopStrategy(4)],
    )

    with pytest.raises(RetryExaustedError) as err:
        await retry(async_func)

    assert isinstance(err.value.__cause__, KeyError)
    assert async_func.call_count == 7
    assert noop.current_attempt == 2
    assert noop_2.current_attempt == 4


@pytest.mark.asyncio
async def test_retry_async_decorator(monkeypatch) -> None:
    monkeypatch.setattr(AsyncRetry, "__call__", mock := AsyncMock())

    async def _test():
        ...

    await retry(strategies=[])(_test)()
    assert mock.call_count == 1


def test_sync_retry_runs_func(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.return_value = 4

    retry = sync_retry()
    result = retry(func)

    assert result == 4
    assert func.call_count == 1


def test_sync_retry_runs_func_with_args(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.return_value = 4

    retry = sync_retry()
    kwargs = dict(a=2, b=2)
    result = retry(func, **kwargs)

    assert result == 4
    assert func.call_count == 1
    assert func.call_args.kwargs == kwargs


def test_sync_retry_raises_exception(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.side_effect = ValueError

    retry = sync_retry()
    with pytest.raises(RetryExaustedError) as err:
        retry(func)

    assert isinstance(err.value.__cause__, ValueError)
    assert func.call_count == 1


def test_sync_raises_exception_on_unmapped_exception(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.side_effect = KeyError

    retry = sync_retry(on_exceptions=[ValueError])
    with pytest.raises(RetryExaustedError) as err:
        retry(func)

    assert isinstance(err.value.__cause__, KeyError)
    assert func.call_count == 1


def test_sync_applies_before_hook(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    hook_mock = MagicMock()

    retry = sync_retry(
        on_exceptions=[KeyError],
        before_hooks=[hook_mock],
    )

    retry(func)
    assert hook_mock.call_count == 1
    assert func.call_count == 1


def test_sync_applies_list_of_before_hooks(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    hooks = []

    for _ in range(5):
        hooks.append(MagicMock())

    retry = sync_retry(
        on_exceptions=[KeyError],
        before_hooks=hooks,
    )

    retry(func)

    for hook in hooks:
        assert hook.call_count == 1
    assert func.call_count == 1


def test_sync_applies_after_hook(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    hook_mock = MagicMock()

    retry = sync_retry(
        on_exceptions=[KeyError],
        after_hooks=[hook_mock],
    )

    retry(func)
    assert hook_mock.call_count == 1
    assert func.call_count == 1


def test_sync_applies_list_of_after_hooks(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.return_value = 1

    hooks = []
    for _ in range(5):
        hooks.append(MagicMock())

    retry = sync_retry(
        on_exceptions=[KeyError],
        after_hooks=hooks,
    )

    retry(func)

    for hook in hooks:
        assert hook.call_count == 1
    assert func.call_count == 1


def test_sync_applies_strategy(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.side_effect = KeyError

    retry = sync_retry(
        strategies=[noop := NoopStrategy(2)],
    )

    with pytest.raises(RetryExaustedError) as err:
        retry(func)

    assert isinstance(err.value.__cause__, KeyError)
    assert func.call_count == 3
    assert noop.current_attempt == 2


def test_sync_applies_multiple_strategies(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.side_effect = KeyError

    retry = sync_retry(
        strategies=[noop := NoopStrategy(2), noop_2 := NoopStrategy(4)],
    )

    with pytest.raises(RetryExaustedError) as err:
        retry(func)

    assert isinstance(err.value.__cause__, KeyError)
    assert func.call_count == 7
    assert noop.current_attempt == 2
    assert noop_2.current_attempt == 4


def test_retry_sync_decorator(monkeypatch) -> None:
    monkeypatch.setattr(Retry, "__call__", mock := MagicMock())

    def _test() -> None:
        pass

    assert retry(strategies=[])(_test)()
    assert mock.call_count == 1


# @patch("time.sleep", return_value=None)
# def test_retry_decorator_sync(
#    patched_time_sleep, retry_sleep: RetrySleepFixtureT
# ) -> None:
#    def _test() -> None:
#        raise ValueError("Something is wrong")
#
#    _, sleep = retry_sleep()
#
#    with pytest.raises(RetryExaustedError) as err:
#        retry(strategies=[sleep])(_test)()
#
#    assert patched_time_sleep.call_count == 3
#    assert patched_time_sleep.call_args.args == (1,)
#    assert sleep.attempts == 3
#    assert isinstance(err.value.__cause__, ValueError)


# @pytest.mark.asyncio
# async def test_async_does_not_retry_on_matches_value_condition(
#     async_retry: AsyncRetrySleepFixtureT,
# ) -> None:
#     async def _test(a: int, b: int) -> int:
#         return a + b
#
#     # TODO: Refactor test to use retry_fixture instead.
#     # This also removes the needs to the type cast + indexes
#     retry = async_retry(type_=int, strategies=[StopWhenReturnValue(4)])
#     result = await retry(_test, a=2, b=2)
#     assert result == 4


## @pytest.mark.asyncio
## async def test_async_retry_raises_on_condition_unmatched() -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     # TODO: Refactor test to use retry_fixture instead.
##     # This also removes the needs to the type cast + indexes
##     retry = AsyncRetry[t.Awaitable[None]](
##         strategies=[StopWhenReturnValue(4, max_attempts=2)]
##     )
##
##     with pytest.raises(RetryExaustedError) as err:
##         await retry(_test, 2)
##
##     assert isinstance(err.value.__cause__, ValueError)
##
##
## @pytest.mark.asyncio
## @pytest.mark.parametrize(("attempts", "expected"), ((1, 1), (2, 2), (3, 3), (10, 10)))
## async def test_async_retry_runs_twice_on_stop_after_attempt(
##     attempts: int,
##     expected: int,
## ) -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     # TODO: Refactor test to use retry_fixture instead.
##     # This also removes the needs to the type cast + indexes
##     retry = AsyncRetry[t.Awaitable[None]](strategies=[StopAfterAttempt(attempts)])
##
##     stop: StopAfterAttempt | None = None
##     with pytest.raises(RetryExaustedError) as err:
##         stop = t.cast(StopAfterAttempt, retry.strategies[0])
##         assert stop.current_attempt == 0
##         await retry(_test, 2)
##
##     assert isinstance(err.value.__cause__, ValueError)
##     assert stop
##     assert stop.should_stop is True
##     assert stop.current_attempt == expected
##
##
## @pytest.mark.asyncio
## @patch("time.sleep", return_value=None)
## @pytest.mark.parametrize(
##     ("seconds", "expected"), ((1.0, 1), (3.0, 2), (5.0, 3), (10.0, 10))
## )
## async def test_async_retry_sleeps_twice_on_sleep_stop(
##     patched_time_sleep,
##     seconds: float,
##     expected: int,
##     async_retry_sleep: AsyncRetrySleepFixtureT,
## ) -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     retry, sleep = async_retry_sleep(seconds=seconds, attempts=expected)
##
##     with pytest.raises(RetryExaustedError) as err:
##         assert sleep.current_attempt == 0
##         await retry(_test, 2)
##
##     assert isinstance(err.value.__cause__, ValueError)
##     assert patched_time_sleep.call_count == expected
##     assert patched_time_sleep.call_args.args == (seconds,)
##
##
## @pytest.mark.asyncio
## @patch("time.sleep", return_value=None)
## @pytest.mark.parametrize(
##     ("seconds", "expected", "attempts"),
##     ((1.0, 1, 1), (3.0, 2, 5), (5.0, 3, 5), (10.0, 10, 6)),
## )
## async def test_async_retry_with_multiple_stops(
##     patched_time_sleep,
##     seconds: float,
##     expected: int,
##     attempts: int,
##     async_retry_sleep: AsyncRetrySleepFixtureT,
## ) -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     retry, sleep = async_retry_sleep(seconds=seconds, attempts=expected)
##     retry.strategies.append(after_attempt := StopAfterAttempt(attempts))
##
##     with pytest.raises(RetryExaustedError) as err:
##         assert sleep.current_attempt == 0
##         assert after_attempt.current_attempt == 0
##
##         await retry(_test, 2)
##
##     assert isinstance(err.value.__cause__, ValueError)
##     assert patched_time_sleep.call_count == expected
##     assert patched_time_sleep.call_args.args == (seconds,)
##
##     assert sleep.should_stop is True
##     assert sleep.current_attempt == expected
##
##     assert after_attempt.current_attempt == attempts
##     assert after_attempt.should_stop is True
##
##
## @pytest.mark.asyncio
## async def test_raises_exception_when_not_in_exception_list(
##     async_retry_sleep: AsyncRetrySleepFixtureT,
## ) -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     retry, sleep = async_retry_sleep()
##     retry.on_exceptions = set((KeyError,))
##
##     with pytest.raises(RetryExaustedError) as err:
##         await retry(_test, 2)
##
##         assert sleep.current_attempt == 0
##
##     assert isinstance(err.value.__cause__, ValueError)
##
##
## @pytest.mark.asyncio
## @patch("time.sleep", return_value=None)
## async def test_raises_applies_strategies_when_in_exception_list(
##     patched_time_sleep, async_retry_sleep: AsyncRetrySleepFixtureT
## ) -> None:
##     async def _test(_: int) -> None:
##         raise ValueError("Something is wrong")
##
##     retry, sleep = async_retry_sleep()
##     retry.on_exceptions = set((ValueError,))
##
##     with pytest.raises(RetryExaustedError) as err:
##         assert sleep.current_attempt == 0
##         await retry(_test, 2)
##
##     assert patched_time_sleep.call_count == 3
##     assert patched_time_sleep.call_args.args == (1,)
##     assert isinstance(err.value.__cause__, ValueError)
##     assert sleep.current_attempt == 3
##
##
## @pytest.mark.asyncio
## @patch("time.sleep", return_value=None)
## async def test_retry_decorator_async(
##     patched_time_sleep, async_retry_sleep: AsyncRetrySleepFixtureT
## ) -> None:
##     async def _test() -> None:
##         raise ValueError("Something is wrong")
##
##     _, sleep = async_retry_sleep()
##
##     with pytest.raises(RetryExaustedError) as err:
##         await retry(strategies=[sleep])(_test)()
##
##     assert patched_time_sleep.call_count == 3
##     assert patched_time_sleep.call_args.args == (1,)
##     assert sleep.attempts == 3
##     assert isinstance(err.value.__cause__, ValueError)
##
##
## @patch("time.sleep", return_value=None)
## def test_retry_decorator_sync(
##     patched_time_sleep, retry_sleep: RetrySleepFixtureT
## ) -> None:
##     def _test() -> None:
##         raise ValueError("Something is wrong")
##
##     _, sleep = retry_sleep()
##
##     with pytest.raises(RetryExaustedError) as err:
##         retry(strategies=[sleep])(_test)()
##
##     assert patched_time_sleep.call_count == 3
##     assert patched_time_sleep.call_args.args == (1,)
##     assert sleep.attempts == 3
##     assert isinstance(err.value.__cause__, ValueError)
##
##
## def test_does_not_retry_on_matches_value_condition(
##     retry_sleep: RetrySleepFixtureT,
## ) -> None:
##     def _test() -> int:
##         return 2
##
##     retry, _ = retry_sleep()
##     result = t.cast(Retry[int], retry)(_test)
##     assert result == 2
