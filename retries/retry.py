#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>

import abc
import functools
import inspect
import typing as t
from dataclasses import dataclass
from datetime import datetime

from retries.exceptions import RetryExaustedError, RetryStrategyExausted
from retries.strategy import Strategy

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]


@dataclass
class RetryState(t.Generic[ReturnT]):
    func: FuncT[ReturnT]
    start_time: int
    strategy_func: Strategy[ReturnT] | None = None
    args: t.Sequence[t.Any] | None = None
    kwargs: t.Dict[str, t.Any] | None = None
    current_attempts: int = 0
    returned_value: ReturnT | None = None
    exception: Exception | None = None

    @property
    def raised(self) -> bool:
        return isinstance(self.exception, Exception)

    def clear(self) -> None:
        self.exception = None
        self.returned_value = None


class BaseRetry(abc.ABC, t.Generic[ReturnT]):
    def __init__(self, strategies: t.Sequence[Strategy[ReturnT]] = []) -> None:
        self.strategies = list(reversed(strategies))

    @abc.abstractmethod
    def __call__(
        self,
        func: FuncT[ReturnT],
        *args: t.Tuple[t.Any],
        **kwargs: t.Dict[t.Any, t.Any],
    ) -> ReturnT | Exception | None:
        raise NotImplementedError

    def save_state(self, state: RetryState[ReturnT]) -> None:
        setattr(state.func, "state", state)

    def exec_strategy(self, state: RetryState[ReturnT]):
        if state.strategy_func is None:
            if len(self.strategies):
                state.strategy_func = self.strategies.pop()
            else:
                raise RetryStrategyExausted

        _pop = lambda l, default: l.pop() if len(l) else default

        state.current_attempts += 1

        try:
            state.strategy_func.maybe_apply(state.returned_value)
        except RetryExaustedError:
            state.strategy_func = _pop(self.strategies, None)


class AsyncRetry(BaseRetry[ReturnT]):
    async def exec(self, state: RetryState[ReturnT]) -> None:
        state.clear()
        try:
            assert inspect.iscoroutinefunction(
                state.func
            ), f"{self.__class__.__name__} needs an awaitable func"

            state.returned_value = await state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            state.exception = err

    async def __call__(
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        while True:
            await self.exec(state)

            try:
                if state.raised:
                    self.exec_strategy(state)
                    continue
                else:
                    self.save_state(state)
                    return state.returned_value
            except RetryStrategyExausted:
                raise RetryExaustedError from state.exception if state.raised else None


class Retry(BaseRetry[ReturnT]):
    def exec(self, state: RetryState[ReturnT]) -> None:
        state.clear()
        try:
            state.returned_value = state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            state.exception = err

    def __call__(
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        while True:
            self.exec(state)

            try:
                if state.raised:
                    self.exec_strategy(state)
                    continue
                else:
                    self.save_state(state)
                    return state.returned_value
            except RetryStrategyExausted:
                raise RetryExaustedError from state.exception if state.raised else None


def retry(strategies: t.Sequence[Strategy]):
    def decorator_retry(
        func: FuncT[ReturnT],
    ) -> FuncT[ReturnT]:
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return AsyncRetry(strategies=strategies)(func, *args, **kwargs)

            return Retry(strategies=strategies)(func, *args, **kwargs)

        return t.cast(FuncT[ReturnT], wrapper_retry)

    return decorator_retry
