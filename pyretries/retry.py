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

from pyretries.exceptions import RetryExaustedError, RetryStrategyExausted
from pyretries.strategy import Strategy

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]
AfterHookFuncT = t.Callable[[Exception | ReturnT], None]
BeforeHookFuncT = t.Callable[..., None]
RetryExceptionCallHook = t.Callable[[Exception], None]


_logger = logging.getLogger(__name__)


@dataclass
class RetryState(t.Generic[ReturnT]):
    """Stores current retry state

    Args:
        func: Function address to retry
        args: `func` non-positional arguments
        kwargs: `func` positional arguments
        start_time: Timestamp when retry first started
        end_time: Timestamp when retry ended
        strategy_func: Next strategy to run
        current_attempts: Number of current retry attempts
        exception: Exception raised by `func`

    """

    func: FuncT[ReturnT]
    start_time: int
    end_time: int = 0
    strategy: Strategy[ReturnT] | None = None
    args: t.Sequence[t.Any] | None = None
    kwargs: t.Dict[str, t.Any] | None = None
    current_attempts: int = 0
    returned_value: ReturnT | None = None
    exception: Exception | None = None

    @property
    def raised(self) -> bool:
        """Checks if `func` raised an exception"""
        return isinstance(self.exception, Exception)

    def clear(self) -> None:
        """Clears retry state"""
        self.exception = None
        self.returned_value = None

    def __repr__(self) -> str:
        cls_name = type(self).__name__
        return (
            f"{cls_name}(start_time={self.start_time}, "
            f"end_time={self.end_time}, "
            f"current_attempts={self.current_attempts}, "
            f"exception={repr(self.exception)}), "
            f"returned_value={self.returned_value})"
        )


class BaseRetry(abc.ABC, t.Generic[ReturnT]):
    """
    Base class for all retry implementations.
    Requires `__call__` implementation

    Examples:
        >>> Class RetryExample(BaseRetry[ReturnT]):
                ...
                def __call__(
                    self,
                    func: FuncT[ReturnT],
                    *args: t.Tuple[t.Any],
                    **kwargs: t.Dict[t.Any, t.Any],
                ) -> ReturnT | Exception | None:
                     ...

    """

    on_exceptions: set[type[Exception]] | None

    def __init__(
        self,
        strategies: t.Sequence[Strategy[ReturnT]] = [],
        on_exceptions: t.Sequence[type[Exception]] | None = None,
        before_hooks: t.Sequence[BeforeHookFuncT] | None = None,
        after_hooks: t.Sequence[AfterHookFuncT[ReturnT]] | None = None,
        retry_exception_hook: RetryExceptionCallHook | None = None,
        should_log: bool = True,
    ) -> None:
        """
        Args:
            strategies: Sequence of retry strategies
            on_exceptions: Sequence of exceptions to apply a retry strategy.
            before_hooks: Hooks to run before running `func`. Runs Before strategy.
            after_hooks: Hooks to run after running `func`. Runs before strategy.
            retry_exception_hook: Hook to run when `func` raised an exception. Runs before strategy.
            should_log: Specifies whether retry should log actions
        """
        self.strategies = list(reversed(strategies))
        self.on_exceptions = set(on_exceptions or []) or None

        self.before_hooks = before_hooks or []
        self.after_hooks = after_hooks or []
        self.retry_exception_hook = retry_exception_hook
        self.should_log = should_log

    @abc.abstractmethod
    def __call__(
        self,
        func: FuncT[ReturnT],
        *args: t.Tuple[t.Any],
        **kwargs: t.Dict[t.Any, t.Any],
    ) -> ReturnT | Exception | None:
        """
        Executes `func` and applies strategies

        Args:
            func: Address to function
            args: `func` non-positional arguments
            kwargs: `func` positional arguments

        """
        raise NotImplementedError

    def save_state(self, state: RetryState[ReturnT]) -> None:
        """
        Saves retry state to `func`

        Args:
            state: Current retry state
        """
        setattr(state.func, "state", state)

    def exec_strategy(self, state: RetryState[ReturnT]):
        """
        Applies user defined strategies.

        Args:
            state: Current retry state

        Raises:
            RetryExaustedError: Raised when strategy is exausted of no strategy is available
        """
        if state.strategy is None:
            if len(self.strategies):
                state.strategy = self.strategies.pop()
            else:
                raise RetryExaustedError

        try:
            if state.strategy.should_stop:
                raise RetryStrategyExausted

            if self.should_log:
                _logger.info(
                    f"Executing '{state.strategy.__class__.__name__}' retry strategy. "
                    f"Current attempt {state.current_attempts}"
                )

            state.strategy.eval(state.returned_value)
            state.current_attempts += 1

            if state.strategy.should_stop:
                state.strategy = None

        except RetryStrategyExausted:
            raise RetryExaustedError

    def apply(self, state: RetryState[ReturnT]) -> bool:
        """
        Checks if last state raised an exception and executes the next available strategy

        Raise `RetryExaustedError` if last executes strategy raised

        Args:
            state: Current retry state

        Raises:
            RetryExaustedError: Raised when `func` exception is not defined in `on_exceptions` sequence
                                or when strategy raises
        """
        try:
            if not state.raised:
                return False

            if (exc := state.exception.__class__) not in (self.on_exceptions or [exc]):
                raise RetryExaustedError from state.exception

            self.exec_strategy(state)
            state.clear()
            return True

        except RetryExaustedError as err:
            raise err from state.exception if state.raised else None

    def _pre_exec(self, _: RetryState[ReturnT]) -> None:
        """
        Should be called before running `func`

        Args:
            state: Current retry state. Currently not used.
        """
        for hook in self.before_hooks:
            hook()

    def _post_exec(
        self, state: RetryState[ReturnT], exception: Exception | None
    ) -> None:
        """
        Should be called after running `func`.
        If exception was raised, this should be passed in `exception` argument.

        Args:
            state: Current retry state. Currently not used.
            exception: Raised exception
        """
        if exception:
            state.exception = exception

            if self.retry_exception_hook:
                self.retry_exception_hook(exception)

        for hook in self.after_hooks:
            hook(state.exception or state.returned_value)

        state.end_time = int(datetime.now().timestamp())


class AsyncRetry(BaseRetry[ReturnT]):
    """
    Asynchronous retry

    Examples:
        >>> async def ok() -> bool:
        ...    return True
        >>> retry = AsyncRetry[t.Awaitable[bool]](strategies=[StopAfterAttemptStrategy(20)])
        >>> print(await retry(ok))
    """

    async def exec(self, state: RetryState[ReturnT]) -> None:
        """
        Executes `func` from `state`

        Args:
            state: Current retry state

        """
        assert inspect.iscoroutinefunction(
            state.func
        ), f"{self.__class__.__name__} needs an awaitable func"

        self._pre_exec(state)

        exception: Exception | None = None
        try:
            state.returned_value = await state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            exception = err

        self._post_exec(state, exception)

    # NOTE: currently, the abtract method is a sync, and here we are defining async.
    # Pyright will alert about this, so we ignore the type for now until we
    # have a fix for it
    async def __call__(  # type:ignore
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        """
        Executes `func` and applies strategies

        Args:
            func: Address to function
            args: `func` non-positional arguments
            kwargs: `func` positional arguments

        Returns:
           Either `func`'s return value or None
        """
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        if self.should_log:
            _logger.info(f"Calling '{func.__name__}'")

        should_reapply = True
        while should_reapply:
            await self.exec(state)

            if not (should_reapply := self.apply(state)):
                break

        self.save_state(state)
        return state.returned_value


class Retry(BaseRetry[ReturnT]):
    """
    Synchronous retry

    Examples:
        >>> def ok() -> bool:
        ...    return True
        >>> retry = Retry[bool](strategies=[StopAfterAttemptStrategy(20)])
        >>> print(retry(ok))
    """

    def exec(self, state: RetryState[ReturnT]) -> None:
        """
        Executes `func` from `state`

        Args:
            state: Current retry state

        """
        self._pre_exec(state)

        exception: Exception | None = None
        try:
            state.returned_value = state.func(
                *(state.args or ()), **(state.kwargs or {})
            )
        except Exception as err:
            exception = err

        self._post_exec(state, exception)

    def __call__(
        self, func: FuncT[ReturnT], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception | None:
        """
        Executes `func` and applies strategies

        Args:
            func: Address to function
            args: `func` non-positional arguments
            kwargs: `func` positional arguments

        Returns:
           Either `func`'s return value or None
        """
        state = RetryState[ReturnT](
            func=func,
            start_time=int(datetime.now().timestamp()),
            args=args,
            kwargs=kwargs,
        )

        if self.should_log:
            _logger.info(f"Calling '{func.__name__}'")

        should_reapply = True
        while should_reapply:
            self.exec(state)

            if not (should_reapply := self.apply(state)):
                break

        self.save_state(state)
        return state.returned_value


def retry(
    strategies: t.Sequence[Strategy] = [],
    on_exceptions: t.Sequence[type[Exception]] | None = None,
    before_hooks: t.Sequence[BeforeHookFuncT] | None = None,
    after_hooks: t.Sequence[AfterHookFuncT[ReturnT]] | None = None,
    retry_exception_hook: RetryExceptionCallHook | None = None,
    should_log: bool = True,
):
    """
    Retry decorator. Works both for sync and async functions

    Examples:
        >>> @retry(strategies=[strategy.NoopStrategy(1)])
        ... def ok() -> bool:
        ...     return True
        >>> ok()
        INFO:retries.retry:Calling 'ok'
        True

    Args:
        strategies: Sequence of retry strategies
        on_exceptions: Sequence of exceptions to apply a retry strategy.
        before_hooks: Hooks to run before running `func`. Runs Before strategy.
        after_hooks: Hooks to run after running `func`. Runs before strategy.
        retry_exception_hook: Hook to run when `func` raised an exception. Runs before strategy.
        should_log: Specifies whether retry should log actions

    Returns:
        func (FuncT[ReturnT]): Functions return value or exception
    """

    def decorator_retry(
        func: FuncT[ReturnT],
    ) -> FuncT[ReturnT]:
        @functools.wraps(func)
        def wrapper_retry(*args, **kwargs):
            if inspect.iscoroutinefunction(func):
                return AsyncRetry(
                    strategies=strategies,
                    on_exceptions=on_exceptions,
                    before_hooks=before_hooks,
                    after_hooks=after_hooks,
                    retry_exception_hook=retry_exception_hook,
                    should_log=should_log,
                )(func, *args, **kwargs)

            return Retry(
                strategies=strategies,
                on_exceptions=on_exceptions,
                before_hooks=before_hooks,
                after_hooks=after_hooks,
                retry_exception_hook=retry_exception_hook,
                should_log=should_log,
            )(func, *args, **kwargs)

        return t.cast(FuncT[ReturnT], wrapper_retry)

    return decorator_retry
