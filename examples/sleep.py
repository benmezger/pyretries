#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:33>

import asyncio
import typing as t

from retries.retry import AsyncRetry
from retries.strategy import Sleep

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1

    if not _counter or _counter == 1:
        raise Exception("Something went wrong")
    return _counter


async def main():
    retry = AsyncRetry[t.Awaitable[int]](
        strategies=[Sleep[int](seconds=1, attempts=3)],
        on_exceptions=[ValueError],
    )

    await retry(make_request)


if __name__ == "__main__":
    asyncio.run(main())
