# standard imports
import datetime

# lib imports
import pytest

# local imports
from src.common import time


@pytest.mark.parametrize("iso_str, expected", [
    ("2024-11-23T20:29:48", datetime.datetime(2024, 11, 23, 20, 29, 48)),
    ("2023-01-01T00:00:00", datetime.datetime(2023, 1, 1, 0, 0, 0)),
    ("2022-12-31T23:59:59", datetime.datetime(2022, 12, 31, 23, 59, 59)),
])
def test_iso_to_datetime(iso_str, expected):
    assert time.iso_to_datetime(iso_str) == expected
