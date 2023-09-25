#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>

import abc
import typing as t

from retries.exceptions import RetryConditionError
from retries.stop import Stop

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]


class Condition(t.Generic[ReturnT]):
    def __init__(self, expected: ReturnT):
        self.expected = expected

    @abc.abstractmethod
    def maybe_apply(self, value: t.Any) -> None:
        raise NotImplementedError


class IsValueCondition(Condition[ReturnT]):
    def maybe_apply(self, value: t.Any) -> None:
        match = value == self.expected
        if not match:
            raise RetryConditionError(f"Expected value {self.expected} but got {value}")


class BaseRetry(abc.ABC, t.Generic[ReturnT]):
    def __init__(self, conditions: t.Sequence[Condition], stop: Stop) -> None:
        self.conditions = conditions
        self.stop = stop

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
        raised_excp: bool = False
        try:
            value = await func(*args, **kwargs)
        except Exception as err:
            raised_excp = True
            value = err

        try:
            for condition in self.conditions:
                condition.maybe_apply(value)
            if raised_excp and isinstance(value, Exception):
                raise value
            return value
        except RetryConditionError:
            self.stop.maybe_apply()
            return await self(func, *args, **kwargs)


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
