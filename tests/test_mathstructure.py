import pytest
from qalculate import (
    ApproximationMode,
    EvaluationOptions,
    MathStructure as S,
    MathFunction as MF,
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
    ],
)
def test_simple_parsing(string: str, expected: S):
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
def test_simple_equations(equation: str, expected: str):
    assert parse(equation).calculate(exact_options).print() == expected


@pytest.mark.parametrize(
    "string,expected",
    [
        ("sin", S.Function(MF.get("sin"))),
        ("gamma10", S.Function(MF.get("gamma"), S.Number(10))),
        ("log(512, 4)", S.Function(MF.get("log"), S.Number(512), S.Number(4))),
    ],
)
def test_function_parsing(string: str, expected: S):
    assert parse(string) == expected
