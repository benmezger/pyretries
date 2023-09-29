#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-25 Mon 21:19>


import abc
import logging
import time
import typing as t

from retries.exceptions import RetryExaustedError

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]
StrategyValueT = t.TypeVar("StrategyValueT")


class Strategy(abc.ABC, t.Generic[StrategyValueT]):
    @abc.abstractproperty
    def should_stop(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def maybe_apply(self, value: StrategyValueT | Exception | None) -> bool:
        raise NotImplementedError


class StopAfterAttempt(Strategy, t.Generic[StrategyValueT]):
    def __init__(self, attempts: int) -> None:
        self.attempts = attempts
        self.current_attempt = 0

    @property
    def should_stop(self) -> bool:
        if self.current_attempt >= self.attempts:
            return True
        return False

    def maybe_apply(self, value: StrategyValueT | Exception | None) -> bool:
        if self.should_stop:
            raise RetryExaustedError from value if isinstance(
                value, Exception
            ) else None

        _logger.info(f"{self.__class__.__name__} is at {self.current_attempt=}")
        self.current_attempt += 1
        return True


class Sleep(Strategy, t.Generic[StrategyValueT]):
    def __init__(self, seconds: float, attempts: int = 1):
        self.seconds = seconds
        self.attempts = attempts
        self.current_attempt = 0

    @property
    def should_stop(self) -> bool:
        if self.current_attempt >= self.attempts:
            return True
        return False

    def maybe_apply(self, value: StrategyValueT | Exception | None) -> bool:
        if self.should_stop:
            raise RetryExaustedError from value if isinstance(
                value, Exception
            ) else None

        self.current_attempt += 1
        _logger.info(
            f"{self.__class__.__name__} {self.current_attempt}/{self.attempts} attempts."
            f" Sleeping for {self.seconds}s"
        )
        time.sleep(self.seconds)

        return True


class StopWhenReturnValue(Strategy, t.Generic[StrategyValueT]):
    def __init__(self, expected: t.Any, max_attempts: int | None = None) -> None:
        self.expected = expected
        self.max_attempts = max_attempts
        self.current_attempt = 0

    @property
    def should_stop(self) -> bool:
        if self.max_attempts is not None:
            if self.current_attempt >= self.max_attempts:
                return True
        return False

    def maybe_apply(self, value: StrategyValueT | Exception | None) -> bool:
        if self.should_stop:
            raise RetryExaustedError from value if isinstance(
                value, Exception
            ) else None

        if self.max_attempts is not None:
            _logger.info(
                f"{self.__class__.__name__} is at {self.current_attempt}/{self.max_attempts}."
            )
            self.current_attempt += 1

        return not value == self.expected
