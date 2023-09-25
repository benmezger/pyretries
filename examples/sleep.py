#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:33>

import asyncio
from typing import cast
from retries.retry import Sleep, AsyncRetry, IsValueCondition

_counter = -1


async def make_request() -> int:
    global _counter
    _counter += 1
    if not _counter:
        raise Exception("Something went wrong")
    return _counter


async def main():
    retry = AsyncRetry[int](
        conditions=[IsValueCondition[int](expected=1)],
        stop=Sleep(seconds=1, attempts=3),
    )

    await retry(make_request)

    assert retry.stop.should_stop == False
    assert cast(Sleep, retry.stop).current_attempt == _counter


if __name__ == "__main__":
    asyncio.run(main())
