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
def test_unit_parsing(text: str, expected: S) -> None:
    assert parse(text) == expected


def test_unit_statics_same_instances() -> None:
    def parse_one(text: str) -> S.Unit:
        x = parse(text)
        assert isinstance(x, S.Unit)
        return x

    assert Unit.DEGREE is parse_one("deg").unit
    assert Unit.RADIAN is parse_one("rad").unit
    assert Unit.GRADIAN is parse_one("gradian").unit
