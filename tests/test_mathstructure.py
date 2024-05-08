from typing import Callable
import pytest
from qalculate import (
    ApproximationMode,
    ComparisonType,
    EvaluationOptions,
    MathStructure as S,
    MathFunction as MF,
    UnknownVariable,
    parse,
)


@pytest.mark.parametrize(
    "string,expected",
    [
        ("20", S.Number(20)),
        (
            "25872955982757432985653786239476225",
            S.Number(25872955982757432985653786239476225),
        ),
        ("23 * 12", S.Multiplication(S.Number(23), S.Number(12))),
        ("23 ** 12", S.Power(S.Number(23), S.Number(12))),
        ("23 xor 12", S.BitwiseXor(S.Number(23), S.Number(12))),
        (
            "23 - 12",
            S.Addition(S.Number(23), S.Multiplication(S.Number(-1), S.Number(12))),
        ),
        (
            "23 / 12",
            S.Multiplication(S.Number(23), S.Power(S.Number(12), S.Number(-1))),
        ),
        # FIXME: Whatever pytest does between evaluating this and calling the test function breaks comparison of Variables!
        #       This is because new variables seem to start pointing to different addresses
        ("x", lambda: S.Variable(UnknownVariable.get("x"))),
        (
            "x² - x + 1 = 0",
            lambda: S.Comparison(
                S.Addition(
                    S.Power(S.Variable(UnknownVariable.get("x")), S.Number(2)),
                    S.Multiplication(
                        S.Number(-1), S.Variable(UnknownVariable.get("x"))
                    ),
                    S.Number(1),
                ),
                ComparisonType.EQUALS,
                S.Number(0),
            ),
        ),
    ],
)
def test_simple_parsing(string: str, expected: S | Callable[[], S]) -> None:
    if not isinstance(expected, S):
        expected = expected()
    assert parse(string) == expected


exact_options = EvaluationOptions(
    approximation=ApproximationMode.EXACT,
)


@pytest.mark.parametrize(
    "equation,expected",
    [
        ("x = 2", "x = 2"),
        ("x² = 4", "x = 2 || x = -2"),
        ("x² - 6x + 9 = 0", "x = 3"),
        ("x² = 3", "x = 3^0.5 || x = (-1) * 3^0.5"),
    ],
)
def test_simple_equations(equation: str, expected: str) -> None:
    assert parse(equation).calculate(exact_options).print() == expected


@pytest.mark.parametrize(
    "string,expected",
    [
        ("sin", S.Function(MF.get("sin"))),
        ("gamma10", S.Function(MF.get("gamma"), S.Number(10))),
        ("log(512, 4)", S.Function(MF.get("log"), S.Number(512), S.Number(4))),
    ],
)
def test_function_parsing(string: str, expected: S) -> None:
    assert parse(string) == expected


@pytest.mark.parametrize(
    "slice",
    [
        slice(1, 2),
        slice(2, 1, -1),
        slice(2, 1, -2),
        slice(2, 1, -3),
        slice(22, 1, -1),
        slice(21, 1, -2),
        slice(20, 1, -3),
        slice(1, 19),
        slice(1, 30),
        slice(-80, -40),
        slice(-40, -80, -2),
        slice(-40, -80),
        slice(50, 20),
        slice(50, 50),
        slice(76, 55),
        slice(6, 81),
        slice(28, 57),
        slice(47, 47),
        slice(89, 86),
        slice(77, 83),
        slice(35, 99),
        slice(83, 51),
        slice(16, 1),
        slice(96, 56),
    ],
)
def test_slicing(slice: slice) -> None:
    ints = [*range(100)]
    structures = S(ints)
    assert ints[slice] == list(map(int, structures[slice]))
