#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:09>

import asyncio
import typing as t

from retries.retry import AsyncRetry
from retries.strategy import StopAfterAttempt

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1

    if _counter % 2:
        raise Exception("Something went wrong")
    if _counter > 8:
        return _counter
    raise Exception("Something went wrong")


async def main():
    retry = AsyncRetry[t.Awaitable[int]](strategies=[StopAfterAttempt(20)])

    print(await retry(make_request))
    assert make_request.state


if __name__ == "__main__":
    asyncio.run(main())
