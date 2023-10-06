#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>

import abc
import functools
import inspect
import logging
import typing as t
from dataclasses import dataclass
from datetime import datetime

from retries.exceptions import RetryExaustedError, RetryStrategyExausted
from retries.strategy import Strategy

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]
AfterHookFuncT = t.Callable[[Exception | ReturnT], None]
BeforeHookFuncT = t.Callable[..., None]


_logger = logging.getLogger(__name__)


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
    on_exceptions: set[type[Exception]] | None

    def __init__(
        self,
        strategies: t.Sequence[Strategy[ReturnT]] = [],
        on_exceptions: t.Sequence[type[Exception]] | None = None,
        before_hooks: t.Sequence[BeforeHookFuncT] | None = None,
        after_hooks: t.Sequence[AfterHookFuncT[ReturnT]] | None = None,
    ) -> None:
        self.strategies = list(reversed(strategies))
        self.on_exceptions = set(on_exceptions or []) or None

        self.before_hooks = before_hooks or []
        self.after_hooks = after_hooks or []

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
                raise RetryExaustedError

        try:
            if state.strategy_func.should_stop:
                raise RetryStrategyExausted

            _logger.info(
                f"Executing '{state.strategy_func.__class__.__name__}' retry strategy. "
                f"Current attempt {state.current_attempts}"
            )

            state.strategy_func.maybe_apply(state.returned_value)
            state.current_attempts += 1

            if state.strategy_func.should_stop:
                state.strategy_func = None

        except RetryStrategyExausted:
            raise RetryExaustedError

    def apply(self, state: RetryState[ReturnT]) -> bool:
        try:
            if state.raised:
                if (exc := state.exception.__class__) not in (
                    self.on_exceptions or [exc]
                ):
                    raise RetryExaustedError from state.exception

                self.exec_strategy(state)
                state.clear()
                return True
            else:
                self.save_state(state)
                return False

        except RetryExaustedError as err:
            raise err from state.exception if state.raised else None


class AsyncRetry(BaseRetry[ReturnT]):
    async def exec(self, state: RetryState[ReturnT]) -> None:
        assert inspect.iscoroutinefunction(
            state.func
        ), f"{self.__class__.__name__} needs an awaitable func"

        for hook in self.before_hooks:
            hook()

        try:
            state.returned_value = await state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            state.exception = err

        for hook in self.after_hooks:
            hook(state.exception or state.returned_value)

    async def __call__(
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        _logger.info(f"Calling '{func.__name__}'")

        should_reapply = True
        while should_reapply:
            await self.exec(state)

            if not (should_reapply := self.apply(state)):
                return state.returned_value


class Retry(BaseRetry[ReturnT]):
    def exec(self, state: RetryState[ReturnT]) -> None:
        for hook in self.before_hooks:
            hook()

        try:
            state.returned_value = state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            state.exception = err

        for hook in self.after_hooks:
            hook(state.exception or state.returned_value)

    def __call__(
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        _logger.info(f"Calling '{func.__name__}'")

        should_reapply = True
        while should_reapply:
            self.exec(state)

            if not (should_reapply := self.apply(state)):
                return state.returned_value


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
