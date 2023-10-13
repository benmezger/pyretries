#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-25 Mon 21:19>


import abc
import logging
import random
import time
import typing as t

from pyretries.exceptions import RetryStrategyExausted

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

ConditionT = t.TypeVar("ConditionT")
ReturnT = t.TypeVar("ReturnT")
FuncT = t.Callable[..., ReturnT]
StrategyValueT = t.TypeVar("StrategyValueT")


class Strategy(abc.ABC, t.Generic[StrategyValueT]):
    """Base Strategy class"""

    def __init__(self, should_log: bool = True) -> None:
        """
        Args:
            should_log: Specifies if strategy should log actions
        """
        self.should_log = should_log

    @abc.abstractproperty
    def should_stop(self) -> bool:
        """
        Checks if strategy should apply
        """
        raise NotImplementedError

    @abc.abstractmethod
    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Returns:
            `True` if it should still be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        raise NotImplementedError


class StopAfterAttemptStrategy(Strategy, t.Generic[StrategyValueT]):
    """
    Stop after attempting N times strategy
    """

    def __init__(self, attempts: int, **kwargs) -> None:
        """
        Args:
            attempts: Number of attempts to run
            kwargs (dict): Passed to base strategy
        """
        self.attempts = attempts
        self.current_attempt = 0
        super().__init__(**kwargs)

    @property
    def should_stop(self) -> bool:
        """Check if strategy should apply.

        Return:
            Returns `True` if current attempt if greater or equal to `attempts`
        """
        if self.current_attempt >= self.attempts:
            return True
        return False

    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Return:
            Returns `True` if strategy should be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        if self.should_stop:
            raise RetryStrategyExausted from value if isinstance(
                value, Exception
            ) else None

        if self.should_log:
            _logger.info(f"{self.__class__.__name__} is at {self.current_attempt=}")

        self.current_attempt += 1
        return True


class SleepStrategy(Strategy, t.Generic[StrategyValueT]):
    """Sleep strategy"""

    def __init__(self, seconds: float, attempts: int = 1, **kwargs):
        """
        Args:
            seconds: Amount of seconds to sleep
            attempts: Number of maximum attempts
            kwargs (dict): Passed to base strategy
        """
        self.seconds = seconds
        self.attempts = attempts
        self.current_attempt = 0
        super().__init__(**kwargs)

    @property
    def should_stop(self) -> bool:
        """Check if strategy should apply.

        Return:
            Returns `True` if current attempt if greater or equal to `attempts`
        """
        if self.current_attempt >= self.attempts:
            return True
        return False

    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Return:
            Returns `True` if strategy should be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        if self.should_stop:
            raise RetryStrategyExausted from value if isinstance(
                value, Exception
            ) else None

        self.current_attempt += 1

        if self.should_log:
            _logger.info(
                f"{self.__class__.__name__} {self.current_attempt}/{self.attempts} attempts."
                f" Sleeping for {self.seconds}s"
            )
        time.sleep(self.seconds)

        return True


class NoopStrategy(Strategy, t.Generic[StrategyValueT]):
    "Do nothing strategy"

    def __init__(self, attempts: int = 1, **kwargs) -> None:
        """
        Args:
            attempts: Number of maximum attempts
            kwargs (dict): Passed to base strategy
        """
        self.attempts = attempts
        self.current_attempt = 0
        super().__init__(**kwargs)

    @property
    def should_stop(self) -> bool:
        """Check if strategy should apply.

        Return:
            Returns `True` if current attempt if greater or equal to `attempts`
        """
        if self.current_attempt >= self.attempts:
            return True
        return False

    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Return:
            Returns `True` if strategy should be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        if self.should_stop:
            raise RetryStrategyExausted from value if isinstance(
                value, Exception
            ) else None

        self.current_attempt += 1
        return True


class StopWhenReturnValueStrategy(Strategy, t.Generic[StrategyValueT]):
    """Stop when return value is X strategy"""

    def __init__(
        self, expected: t.Any, max_attempts: int | None = None, **kwargs
    ) -> None:
        """
        Args:
            expected: Expected return value
            max_attempts: Number of maximum attempts. By default it runs forever
            kwargs (dict): Passed to base strategy
        """
        self.expected = expected
        self.max_attempts = max_attempts
        self.current_attempt = 0
        super().__init__(**kwargs)

    @property
    def should_stop(self) -> bool:
        """Check if strategy should apply.

        Return:
            Returns `True` if current attempt if greater or equal to `attempts`
        """
        if self.max_attempts is not None:
            if self.current_attempt >= self.max_attempts:
                return True
        return False

    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Return:
            Returns `True` if strategy should be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        if self.should_stop:
            raise RetryStrategyExausted from value if isinstance(
                value, Exception
            ) else None

        if self.max_attempts is not None:
            if self.should_log:
                _logger.info(
                    f"{self.__class__.__name__} is at {self.current_attempt}/{self.max_attempts}."
                )
            self.current_attempt += 1

        return not value == self.expected


class ExponentialBackoffStrategy(Strategy, t.Generic[StrategyValueT]):
    """Exponential backoff strategy"""

    def __init__(self, max_attempts: int, base_delay: float, **kwargs) -> None:
        """
        Args:
            max_attempts: Number of maximum attempts
            base_delay: base delay in seconds for exponential backoff
            kwargs (dict): Passed to base strategy
        """
        self.base_delay = base_delay
        self.max_attempts = max_attempts
        self.current_attempt = 0
        self.delay = 0
        super().__init__(**kwargs)

    @property
    def should_stop(self) -> bool:
        """Check if strategy should apply.

        Return:
            Returns `True` if current attempt if greater or equal to `attempts`
        """
        if self.current_attempt >= self.max_attempts:
            return True
        return False

    def eval(self, value: StrategyValueT | Exception | None) -> bool:
        """
        Evaluates strategy.

        Args:
            value: `func` Returned value or exception.

        Return:
            Returns `True` if strategy should be applied in the next iteration

        Raises:
            RetryStrategyExausted: Raised when strategy is exausted
        """
        if self.should_stop:
            raise RetryStrategyExausted from value if isinstance(
                value, Exception
            ) else None

        self.current_attempt += 1
        self.delay = self.base_delay * 2**self.current_attempt + random.uniform(0, 1)

        if self.should_log:
            _logger.info(
                f"{self.__class__.__name__} {self.current_attempt}/{self.max_attempts} attempts."
                f" Sleeping for {self.delay:.2f}s"
            )

        time.sleep(self.delay)
        return True
