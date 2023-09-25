#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-25 Mon 21:19>


import abc
import time
import typing as t

from retries.exceptions import RetryExaustedError

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]


class Stop(abc.ABC):
    @abc.abstractproperty
    def should_stop(self) -> bool:
        raise NotImplementedError

    @abc.abstractmethod
    def maybe_apply(self) -> None:
        raise NotImplementedError


class StopAfterAttempt(Stop):
    def __init__(self, attempts: int) -> None:
        self.attempts = attempts
        self.current_attempt = 0

    @property
    def should_stop(self) -> bool:
        if self.current_attempt >= self.attempts:
            return True
        return False

    def maybe_apply(self) -> None:
        if self.should_stop:
            raise RetryExaustedError from None
        self.current_attempt += 1


class Sleep(Stop):
    def __init__(self, seconds: float, attempts: int = 1):
        self.seconds = seconds
        self.attempts = attempts
        self.current_attempt = 0

    @property
    def should_stop(self) -> bool:
        if self.current_attempt >= self.attempts:
            return True
        return False

    def maybe_apply(self) -> None:
        if self.should_stop:
            raise RetryExaustedError from None

        self.current_attempt += 1
        time.sleep(self.seconds)
