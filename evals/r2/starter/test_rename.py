"""Oracle for R2: green only after the rename in both files."""
from a import AMOUNT
from b import get


def test_rename():
    assert AMOUNT == 1
    assert get() == 1
