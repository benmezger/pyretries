#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-23 Sat 21:35>


class RetryExaustedError(BaseException):
    """Raised when the number of retries was exausted"""

    ...


class RetryStrategyExausted(BaseException):
    """Raised when the strategy was exausted"""

    ...
