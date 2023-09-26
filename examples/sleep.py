#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:33>

import asyncio
from typing import cast

from retries.retry import AsyncRetry
from retries.stop import Sleep

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1

    if not _counter or _counter == 1:
        raise Exception("Something went wrong")
    return _counter


async def main():
    retry = AsyncRetry[int](
        stops=[Sleep[int](seconds=1, attempts=3)],
    )

    await retry(make_request)

    stop = cast(Sleep, retry.stops[0])
    assert stop.should_stop == False
    assert stop.current_attempt == _counter


if __name__ == "__main__":
    asyncio.run(main())
