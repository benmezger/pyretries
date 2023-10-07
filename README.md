# PyRetries

![Github actions](https://github.com/benmezger/pyretries/actions/workflows/main.yml/badge.svg)
[![codecov](https://codecov.io/gh/benmezger/pyretries/graph/badge.svg?token=E9gAEDW4qT)](https://codecov.io/gh/benmezger/pyretries)

A retry library for Python. This library allows:

1. Creating custom strategies
1. Applying hooks before and after executing function (useful for custom logging)
1. Applying hook to when function raised an error (useful for incriminating metrics)
1. Applying multiple retry strategies
1. Fully typed

See [documentation](https://benmezger.github.io/pyretries/) for more information.

## Installing

The package is available through [Pypi](https://pypi.org/project/pyretries/). You can install using `pip` or any of your favorite package manager:

```shell
pip install pyretries
```

Or using `poetry`

```shell
poetry add pyretries
```
