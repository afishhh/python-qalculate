from typing import Callable
import pytest
from qalculate import Number
from random import randint


def test_small_conversion():
    for _ in range(1000):
        value = randint(-(2**60), 2**60)
        assert int(Number(value)) == value


def test_big_conversion():
    for _ in range(1000):
        value = randint(-(2**100), 2**100)
        assert int(Number(value)) == value


@pytest.mark.parametrize(
    "num_op,int_op,exp",
    [
        (Number.__add__, int.__add__, False),
        (Number.__sub__, int.__sub__, False),
        (Number.__mul__, int.__mul__, False),
        (Number.__gt__, int.__gt__, False),
        (Number.__lt__, int.__lt__, False),
        (Number.__pow__, int.__pow__, True),
    ],
)
def test_operation(
    num_op: Callable[[Number, Number], Number],
    int_op: Callable[[int, int], int],
    exp: bool,
):
    for _ in range(100):
        if exp:
            a = randint(-(2**10), 2**10)
            b = randint(0, 2**10)
        else:
            a = randint(-(2**100), 2**100)
            b = randint(-(2**100), 2**100)

        qa = Number(a)
        qb = Number(b)

        result = num_op(qa, qb)
        if isinstance(result, Number):
            result = int(result)
        assert result == int_op(a, b)
