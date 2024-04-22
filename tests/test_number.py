from typing import Callable
import pytest
from qalculate import Number
from random import randint
import math


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
        (Number.__eq__, int.__eq__, False),
        (Number.__pow__, int.__pow__, True),
    ],
)
def test_int_operations(
    num_op: Callable[[Number, Number], Number],
    int_op: Callable[[int, int], int],
    exp: bool,
):
    def test_one_op(a: int, b: int):
        qa = Number(a)
        qb = Number(b)

        result = num_op(qa, qb)
        if isinstance(result, Number):
            result = int(result)
        assert result == int_op(a, b)

    test_one_op(0, 0)
    test_one_op(1, 0)
    test_one_op(70, 0)
    test_one_op(70, 60)
    test_one_op(61789, 61789)

    for _ in range(100):
        if exp:
            a = randint(-(2**10), 2**10)
            b = randint(0, 2**10)
        else:
            a = randint(-(2**100), 2**100)
            b = randint(-(2**100), 2**100)

        test_one_op(a, b)


comparison_test_values = [0, math.inf, -math.inf, 10, 300, 6728, 15632]


@pytest.mark.parametrize("a", comparison_test_values)
@pytest.mark.parametrize("b", comparison_test_values)
@pytest.mark.parametrize(
    "op", ["__eq__", "__mul__", "__lt__", "__gt__", "__add__", "__sub__"]
)
def test_float_operations(a: int | float, b: int | float, op: str):
    if isinstance(a, int):
        a = float(a)
    if isinstance(b, int):
        b = float(b)

    expected = float.__dict__[op](a, b)

    if math.isnan(expected):
        with pytest.raises(ValueError):
            Number.__dict__[op](Number(a), Number(b))
    else:
        assert Number.__dict__[op](Number(a), Number(b)) == expected
