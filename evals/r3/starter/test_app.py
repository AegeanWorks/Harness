"""Oracle for R3: green only when the off-by-one is fixed."""
from app import total


def test_total():
    assert total([1, 2, 3]) == 6
