#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>

import abc
import typing as t

from retries.exceptions import RetryConditionError, RetryExaustedError
from retries.stop import Stop

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]


class BaseRetry(abc.ABC, t.Generic[ReturnT]):
    def __init__(self, stops: t.Sequence[Stop[ReturnT]] = []) -> None:
        self.stops = list(stops)
        self._applied_stops = list[Stop[ReturnT]]()

    @abc.abstractmethod
    def __call__(
        self,
        func: FuncT[ReturnT],
        *args: t.Tuple[t.Any],
        **kwargs: t.Dict[t.Any, t.Any],
    ) -> ReturnT | Exception:
        raise NotImplementedError


# class Retry(BaseRetry[ReturnT]):
#     def __call__(
#         self,
#         func: FuncT[ReturnT],
#         *args: t.Tuple[t.Any],
#         **kwargs: t.Dict[t.Any, t.Any]
#     ) -> ReturnT | Exception:
#         try:
#             return func(*args, **kwargs)
#         except Exception as err:
#             return err


class AsyncRetry(BaseRetry[ReturnT]):
    async def __call__(
        self, func: FuncT[t.Awaitable[ReturnT]], *args: t.Any, **kwargs: t.Any
    ) -> ReturnT | Exception:
        raised_excp: bool
        value: ReturnT | Exception

        while True:
            try:
                value = await func(*args, **kwargs)
                raised_excp = False

                self.stops.extend(self._applied_stops)
                return value
            except Exception as err:
                raised_excp = True
                value = err

            try:
                if self._apply_stop_conditions(value):
                    continue

                self.stops.extend(self._applied_stops)
                if raised_excp and isinstance(value, Exception):
                    raise value
                return value
            except RetryExaustedError:
                pass

    def _apply_stop_conditions(self, value: ReturnT | Exception):
        excp: RetryExaustedError | None = None

        for stop in self.stops:
            try:
                if stop.maybe_apply(value):
                    return True
            except RetryExaustedError as err:
                self._applied_stops.append(stop)
                self.stops.remove(stop)

                excp = err
                continue

        if excp is not None:
            raise excp


# ParamT = t.ParamSpec("ParamT")
# DecoratedFunc = t.Callable[[FuncT[ParamT]], Awaitable[ReturnT]]
# DecoratorFuncT = t.Callable[[FuncT], ReturnT]
#
#
# async def retry(
#     conditions: t.Sequence[Condition],
# ) -> DecoratorFuncT:
#     def decorator_retry(
#         func: t.Awaitable[ReturnT],
#     ) -> t.Callable[..., t.Awaitable[ReturnT]]:
#         @functools.wraps(func)
#         async def wrapper_retry(*args, **kwargs) -> ReturnT | Exception:
#             retry = AsyncRetry[ReturnT](conditions=conditions)
#             return await retry(func, *args, **kwargs)
#
#         return wrapper_retry
#
#     return decorator_retry
#
#
# @retry(conditions=[])
# async def test(a: int) -> int:
#     return a
