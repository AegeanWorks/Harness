"""Oracle for R1: green only when bug.py is fixed."""
from bug import add


def test_add():
    assert add(1, 1) == 2
