#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:33>

import asyncio
import typing as t

from retries.retry import AsyncRetry
from retries.strategy import ExponentialBackoffStrategy

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1

    if not _counter or _counter == 1:
        raise ValueError("Something went wrong")
    return _counter


async def ok() -> bool:
    return True


async def main():
    retry = AsyncRetry[t.Awaitable[int]](
        strategies=[ExponentialBackoffStrategy[int](max_attempts=3, base_delay=2)],
        on_exceptions=[ValueError],
    )

    print(await retry(make_request))

    retry = AsyncRetry[t.Awaitable[bool]](
        strategies=[ExponentialBackoffStrategy[bool](max_attempts=3, base_delay=2)],
        on_exceptions=[ValueError],
    )

    print(await retry(ok))


if __name__ == "__main__":
    asyncio.run(main())
