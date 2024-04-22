import pytest
from qalculate import parse, Variable, UnknownVariable, load_global_variables

load_global_variables()


@pytest.mark.parametrize(
    "string,var_name",
    [
        ("x", "x"),
        ("y", "y"),
        ("pi", "pi"),
        ("π", "pi"),
        ("pi", "π"),
    ],
)
def test_builtin_variables(string: str, var_name: str):
    assert parse(string).variable is Variable.get(var_name)
