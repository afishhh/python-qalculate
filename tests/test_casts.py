from typing import Any, Callable
import qalculate as q
import pytest


def add_to_mathstructure(value: Any) -> q.MathStructure:
    return q.MathStructure(0) / value

@pytest.mark.parametrize(
    "fun", [q.MathStructure, q.calculate, add_to_mathstructure]
)
@pytest.mark.parametrize("value", [1, 1.0, 2 + 1j, [1 + 2j], [20, [10]]])
def test_casts_to_mathstructure(fun: Callable[[Any], Any], value: Any):
    if (
        fun in (q.calculate, add_to_mathstructure)
        and isinstance(value, list)
        and any(isinstance(el, list) for el in value)
    ):
        pytest.xfail("q.calculate does not handle lists with lists properly")
    fun(value)


@pytest.mark.parametrize(
    "fun",
    [
        q.Number,
        lambda x: q.Number(2) + x,
        lambda x: q.Number(2) < x,
        lambda x: q.Number(2).pow(x),
        lambda x: q.Number(2).exp10(x),
    ],
)
@pytest.mark.parametrize("value", [1, 1.0, 2 + 1j])
def test_casts_to_number(fun: Callable[[Any], Any], value: Any):
    fun(value)
