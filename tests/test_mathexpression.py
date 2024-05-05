import pytest
from qalculate import ExpressionItem, Unit, parse, Variable, load_global_variables, load_global_units

load_global_variables()
load_global_units()

@pytest.mark.parametrize(
    "class_,name",
    [
        (Variable, "x"),
        (Variable, "y"),
        (Unit, "s"),
        (Unit, "m"),
        (Unit, "deg"),
    ]
)
def test_same_instances(class_: type[ExpressionItem], name: str) -> None:
    a = class_.get(name)
    b = class_.get(name)
    c = class_.get(name)
    d = getattr(parse(name), class_.__name__.lower())
    assert isinstance(d, class_)
    assert a is b
    assert a is c
    assert a is d

def test_variable_proxy_compare() -> None:
    assert parse("x") == parse("x")
