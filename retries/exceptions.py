#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>


class RetryExaustedError(BaseException):
    """Raised when the number of retries was exausted"""

    ...


class RetryConditionError(BaseException):
    """Raised when a condition does not apply to a given value"""

    ...


class RetryStopExausted(BaseException):
    ...
