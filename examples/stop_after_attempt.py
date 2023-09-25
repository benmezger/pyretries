#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-24 Sun 22:09>

import asyncio
from typing import cast
from retries.retry import AsyncRetry, IsValueCondition
from retries.stop import StopAfterAttempt


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
    retry = AsyncRetry[int](
        conditions=[IsValueCondition[int](10)], stop=StopAfterAttempt(20)
    )

    await retry(make_request)

    assert retry.stop.should_stop == False
    assert cast(StopAfterAttempt, retry.stop).current_attempt == _counter


if __name__ == "__main__":
    asyncio.run(main())
