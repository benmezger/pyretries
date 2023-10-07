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
    BeforeHookFuncT,
    Retry,
    RetryExceptionCallHook,
    RetryState,
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
        retry_exception_hook: RetryExceptionCallHook | None = None,
    ) -> AsyncRetry[t.Any]:
        return AsyncRetry[t.Any](
            strategies=strategies or [],
            on_exceptions=on_exceptions,
            before_hooks=before_hooks or [],
            after_hooks=after_hooks or [],
            retry_exception_hook=retry_exception_hook,
        )

    return _async_retry


@pytest.fixture
def sync_retry():
    def _sync_retry(
        strategies: list[Strategy[t.Any]] | None = None,
        on_exceptions: list[type[Exception]] | None = None,
        before_hooks: list[BeforeHookFuncT] | None = None,
        after_hooks: list[AfterHookFuncT] | None = None,
        retry_exception_hook: RetryExceptionCallHook | None = None,
    ) -> Retry[t.Any]:
        return Retry[t.Any](
            strategies=strategies or [],
            on_exceptions=on_exceptions,
            before_hooks=before_hooks or [],
            after_hooks=after_hooks or [],
            retry_exception_hook=retry_exception_hook,
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
async def test_async_sets_state(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    async_func.return_value = 4

    retry = async_retry()
    await retry(async_func)

    state: RetryState = async_func.state
    state.returned_value = 4


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
async def test_async_applies_exception_hook(
    async_retry: t.Callable[..., AsyncRetry[t.Any]], async_func: AsyncMock
) -> None:
    hook_mock = MagicMock()
    async_func.side_effect = ValueError

    retry = async_retry(
        retry_exception_hook=hook_mock,
    )

    with pytest.raises(RetryExaustedError):
        await retry(async_func)

    assert hook_mock.call_count == 1
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


def test_sync_sets_state(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    func.return_value = 4

    retry = sync_retry()
    retry(func)

    state: RetryState = func.state
    state.returned_value = 4


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


def test_sync_applies_exception_hook(
    sync_retry: t.Callable[..., Retry[t.Any]], func: MagicMock
) -> None:
    hook_mock = MagicMock()
    func.side_effect = ValueError

    retry = sync_retry(
        retry_exception_hook=hook_mock,
    )

    with pytest.raises(RetryExaustedError):
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


def test_retry_state_repr():
    state = RetryState(lambda: None, 1, returned_value=1, exception=ValueError("ABC"))
    assert (
        repr(state)
        == "RetryState(start_time=1, current_attempts=0, exception=ValueError('ABC')), returned_value=1)"
    )
