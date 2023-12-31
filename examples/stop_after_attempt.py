#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:09>

import asyncio
import typing as t

from pyretries.retry import AsyncRetry
from pyretries.strategy import StopAfterAttemptStrategy

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1

    if _counter % 2:
        raise Exception("Something went wrong")
    if _counter > 8:
        return _counter
    raise Exception("Something went wrong")


async def ok() -> bool:
    return True


async def main():
    retry = AsyncRetry[t.Awaitable[int]](strategies=[StopAfterAttemptStrategy(20)])

    print(await retry(make_request))

    retry = AsyncRetry[t.Awaitable[bool]](strategies=[StopAfterAttemptStrategy(20)])

    print(await retry(ok))


if __name__ == "__main__":
    asyncio.run(main())
