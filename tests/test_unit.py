from qalculate import Unit, parse, MathStructure as S, load_global_units
import pytest

load_global_units()


@pytest.mark.parametrize(
    "text,expected",
    [
        ("deg", S.Unit(Unit.DEGREE)),
        ("rad", S.Unit(Unit.RADIAN)),
        ("gradian", S.Unit(Unit.GRADIAN)),
        ("10m", S.Multiplication(S.Number(10), S.Unit(Unit.get("meter")))),
        ("sm", S.Multiplication(S.Unit(Unit.get("second")), S.Unit(Unit.get("meter")))),
    ],
)
def test_unit_parsing(text: str, expected: S):
    assert parse(text) == expected


def test_unit_statics_same_instances():
    assert Unit.DEGREE is parse("deg").unit
    assert Unit.RADIAN is parse("rad").unit
    assert Unit.GRADIAN is parse("gradian").unit
