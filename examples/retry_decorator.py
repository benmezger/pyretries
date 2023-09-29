#!/usr/bin/env python3

# Author: Ben Mezger <me@benmezger.nl>
# Created at <2023-09-28 Thu 23:23>

import asyncio

from retries.retry import retry
from retries.strategy import StopAfterAttempt

_counter = -1


@retry(strategies=[StopAfterAttempt(20)])
def _make_request() -> int:
    global _counter
    _counter += 1

    if _counter % 2:
        raise Exception("Something went wrong")
    if _counter > 8:
        return _counter
    raise Exception("Something went wrong")


async def make_request() -> int:
    return _make_request()


def make_sync_request() -> int:
    return _make_request()


async def main():
    global _counter

    print(await make_request())

    _counter = 0
    print(make_sync_request())


if __name__ == "__main__":
    asyncio.run(main())
