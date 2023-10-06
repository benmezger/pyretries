import time
from unittest.mock import MagicMock

import pytest


@pytest.fixture
def sleep(monkeypatch) -> MagicMock:
    monkeypatch.setattr(time, "sleep", mock := MagicMock())
    mock.return_value = None
    return mock
