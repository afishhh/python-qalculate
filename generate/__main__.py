from io import StringIO
from typing import Literal
from pathlib import Path
import re
from contextlib import contextmanager
import sys

from generate.bindings import KW_ONLY, PyClass, PyContext
from generate.merge_types import merge_typing_files
from generate.output import OutputDirectory

from .parsing import (
    Accessibility,
    Parameter,
    ParsedSourceFiles,
    PointerType,
    SimpleType,
    Struct,
    Type,
)
from .utils import *

libqalculate_src = Path(sys.argv[1]) / "libqalculate"
output_directory = OutputDirectory(Path(sys.argv[2]))
types_output = (
    Path(sys.argv[3]) if len(sys.argv) >= 4 else output_directory.path / "types.pyi"
)
qalculate_sources = ParsedSourceFiles(libqalculate_src.glob("*.h"))


def prepare_impl_file(text: TextIO, includes: list[str] = []) -> IndentedWriter:
    writer = IndentedWriter(text)
    includes += ["<pybind11/pybind11.h>", "<libqalculate/qalculate.h>"]
    for include in includes:
        writer.write(f"#include {include}\n")
    return writer


MATH_STRUCTURE_CLASS = "qalc_class_<MathStructure>"

header = IndentedWriter(output_directory.writer("generated.hh"))
impl = IndentedWriter(output_directory.writer("generated.cc"))
typings = prepare_impl_file(StringIO())

typings.write("import typing\n")
typings.write("from typing import overload\n")

classes = PyContext(qalculate_sources)
MathStructure = classes.add("MathStructure", holder="QalcRef<MathStructure>")
classes.add("ExpressionItem", holder="QalcRef<ExpressionItem>")
classes.add("Assumptions", wrapper="class PAssumptions")
classes.add("ExpressionName")
classes.add("Unit", holder="QalcRef<Unit>", bases=["ExpressionItem"])
classes.add(
    "EvaluationOptions",
    wrapper="class PEvaluationOptions",
)
classes.add(
    "MathFunction",
    holder="QalcRef<MathFunction>",
    bases=["ExpressionItem"],
)
Number = classes.add("Number")
classes.add("SortOptions")
classes.add("PrintOptions")
classes.add("ParseOptions")

classes.add_foreign("MathStructureRef", "MathStructure")
classes.add_implcit_cast("int", "Number")
classes.add_implcit_cast("float", "Number")
classes.add_implcit_cast("complex", "Number")
classes.add_implcit_cast("int", "MathStructure")
classes.add_implcit_cast("float", "MathStructure")
classes.add_implcit_cast("complex", "MathStructure")
classes.add_implcit_cast("list[MathStructure]", "MathStructure")
classes.add_implcit_cast("Variable", "MathStructure")
classes.add_implcit_cast("MathFunction", "MathStructure")

class_extra_impl: dict[PyClass, str] = {}

header.write(
    """
#pragma once
#include "proxies.hh"
#include <pybind11/operators.h>
#include <pybind11/pybind11.h>
#include <libqalculate/qalculate.h>
#include "ref.hh"
"""
)

impl.write('#include "generated.hh"\n\n')


@contextmanager
def function_declaration(signature: str, impl=impl):
    header.write(f"{signature};\n")
    impl.write(f"{signature} {{\n")
    impl.indent()
    yield
    impl.dedent()
    impl.write(f"}}\n")


def iter_properties(
    struct: Struct, *, require_getter_const: bool = True, exclude: set[str] = set()
):
    for member in struct.methods.values():
        if (
            member.params == []
            and (member.const or not require_getter_const)
            and not member.is_operator
            and not member.name in exclude
            and member.return_type != SimpleType("void")
        ):
            yield member


def properties_for(
    pyclass: PyClass,
    *,
    allow_readwrite: bool = False,
    require_getter_const: bool = True,
    renames: dict[str, str | None] = {},
    extra_for_repr: Iterable[str] = [],
    add_repr_from_rw: bool = False,
):
    struct = pyclass.underlying_type
    added_rw_props = list(extra_for_repr)

    for member in iter_properties(struct, require_getter_const=require_getter_const):
        mapped = renames.get(member.name, camel_to_snake(member.name))
        if mapped is None:
            continue

        setter = struct.methods.get(f"set{camel_to_pascal(member.name)}", None)

        property = pyclass.property(mapped, docstring=member.docstring)
        property.getter(
            f"&{pyclass.underlying_name}::{member.name}", type=member.return_type
        )
        if setter and len(setter.params) == 1 and allow_readwrite:
            assert not setter.variadic
            property.setter(
                f"&{pyclass.underlying_name}::{setter.name}",
                param_type=setter.params[0].type,
            )
            added_rw_props.append(mapped)

    if add_repr_from_rw:
        define_repr_from_props(
            pyclass,
            added_rw_props,
        )


def define_repr_from_props(pyclass: PyClass, properties: Iterable[str]):
    with pyclass.method(
        "std::string", "__repr__", operator=True, receiver="pybind11::object s"
    ) as body:
        body.write(f'std::string output = "{pyclass.name}(";\n')
        body.write(f"output.reserve(512);\n")
        for i, name in enumerate(properties):
            if i != 0:
                body.write(f'output += ", ";\n')
            body.write(f'output += "{name}=";\n')
            body.write(
                f'output += s.attr("{name}").attr("__repr__")().cast<std::string_view>();\n'
            )
        body.write("return output;\n")


def options(
    pyclass: PyClass,
    *,
    exclude: set[str] = set(),
    define_new_default=False,
    pass_by_type: dict[str, str] = {},
):
    defaults_name = f"global_{pascal_to_snake(pyclass.name)}"

    if define_new_default:
        class_extra_impl.setdefault(pyclass, "")
        defaults_name = f"_autogen_{pascal_to_snake(pyclass.name)}_defaults"
        class_extra_impl[pyclass] += f"{pyclass.name} {defaults_name};\n"

    options = {}
    for field in pyclass.underlying_type.fields.values():
        if field.accessibility != Accessibility.PUBLIC:
            continue

        if field.name in exclude:
            continue

        pyclass.field(
            field.type,
            camel_to_snake(field.name),
            field.name,
            mode="readwrite",
            docstring=field.docstring,
        )

        options[field.name] = field.type

    parameters = [
        Parameter(
            type=Type.parse(pass_by_type.get(str(type), str(type))),
            name=name,
            default=f"{defaults_name}.{name}",
        )
        for name, type in options.items()
    ]

    with pyclass.init(KW_ONLY, *parameters) as body:
        body.write(f"{pyclass.implementation_name} result;\n")
        for field in options.keys():
            body.write(f"result.{field} = {field};\n")
        body.write(f"return result;\n")

    define_repr_from_props(
        pyclass,
        options.keys(),
    )


enums: list[str] = []


def enum(name: str, prefix: str | None = None, writer: IndentedWriter = impl):
    enums.append(name)
    classes.add_foreign(name, name)
    enum = qalculate_sources.enum(name)
    if prefix is None:
        prefix = f"{pascal_to_snake(name).upper()}_"

    typings.indent(f"class {name}:\n")

    with function_declaration(
        f"pybind11::enum_<{name}> add_{pascal_to_snake(name)}_enum(pybind11::module_ &m)",
        impl=writer,
    ):
        with writer.indent(f'return pybind11::enum_<{name}>(m, "{name}")\n'):
            for variant in enum.members:
                docarg = (
                    f", {cpp_string(variant.docstring)}" if variant.docstring else ""
                )
                pyvariant = variant.name.removeprefix(prefix)
                writer.write(f'.value("{pyvariant}", {name}::{variant.name}{docarg})\n')
                typings.write(f"{pyvariant}: typing.ClassVar[{name}]\n")
        writer.write(";\n")

    typings.write(f"__members__: typing.ClassVar[dict[str, {name}]]\n")

    # TODO: Generate these members for enums (pybind11-stubgen does)
    # def __eq__(self, other: typing.Any) -> bool:
    #     ...
    # def __getstate__(self) -> int:
    #     ...
    # def __hash__(self) -> int:
    #     ...
    # def __index__(self) -> int:
    #     ...
    # def __init__(self, value: int) -> None:
    #     ...
    # def __int__(self) -> int:
    #     ...
    # def __ne__(self, other: typing.Any) -> bool:
    #     ...
    # def __setstate__(self, state: int) -> None:
    #     ...

    typings.write(f"@property\n")
    typings.write(f"def name(self) -> str: ...\n")
    typings.write(f"@property\n")
    typings.write(f"def value(self) -> int: ...\n")
    typings.write(f"def __str__(self) -> str: ...\n")
    typings.write(f"def __repr__(self) -> str: ...\n")
    typings.dedent()


with output_directory.writer("enums.cc") as writer:
    writer = prepare_impl_file(writer)
    enum("ApproximationMode", "APPROXIMATION_", writer)
    enum("NumberFractionFormat", "FRACTION_", writer)
    enum("StructuringMode", "STRUCTURING_", writer)
    enum("AutoPostConversion", "POST_CONVERSION_", writer)
    enum("ComparisonType", "COMPARISON_", writer)
    enum("RoundingMode", "ROUNDING_", writer)
    enum("MessageType", "MESSAGE_", writer)
    enum("AutomaticFractionFormat", "AUTOMATIC_FRACTION_", writer)
    enum("AutomaticApproximation", "AUTOMATIC_APPROXIMATION_", writer)
    for name in (
        "MultiplicationSign",
        "DivisionSign",
        "BaseDisplay",
        "DigitGrouping",
        "TimeZone",
        "ExpDisplay",
        "ReadPrecisionMode",
        "AngleUnit",
        "IntervalCalculation",
        "ComplexNumberForm",
        "MixedUnitsConversion",
        "ParsingMode",
        "DateTimeFormat",
        "IntervalDisplay",
        "ComparisonResult",
        "AssumptionType",
        "AssumptionSign",
    ):
        enum(name, writer=writer)

    # This one is initialized manually (to add helper properties)
    enums.remove("ComparisonResult")
    with function_declaration("void add_all_enums(pybind11::module_ &m)", impl=writer):
        for enm in enums:
            writer.write(f"add_{pascal_to_snake(enm)}_enum(m);\n")

impl.write('#include "wrappers.hh"\n')
impl.write('#include "options.hh"\n')

options(classes["SortOptions"])
options(
    classes["PrintOptions"],
    exclude={
        "prefix",
        "is_approximate",
        "can_display_unicode_string_arg",
        "can_display_unicode_string_function",
    },
)
options(classes["ParseOptions"], exclude={"unended_function", "default_dataset"})
options(
    classes["EvaluationOptions"],
    exclude={"isolate_var", "protected_function"},
)


properties_for(
    classes["Number"],
    renames={
        "llintValue": None,
        "floatValue": None,
        "integer": None,
        "getBoolean": None,
        "internalType": None,
        "internalRational": None,
        "internalLowerFloat": None,
        "internalUpperFloat": None,
    },
)

number_operators = [
    ("Number", "multiply", "__mul__"),
    ("Number", "divide", "__truediv__"),
    ("Number", "add", "__add__"),
    ("Number", "subtract", "__sub__"),
    ("Number", "bitXor", "__xor__"),
    ("bool", "isLessThan", "__lt__"),
    ("bool", "isLessThanOrEqualTo", "__le__"),
    ("bool", "isGreaterThan", "__gt__"),
    ("bool", "isGreaterThanOrEqualTo", "__ge__"),
    ("Number", "raise", "__pow__"),
]

for ret, cpp_function, py_op in number_operators:
    with Number.method(ret, py_op, "Number const& other", operator=True) as body:
        if ret == "Number":
            body.write(f"Number result = self;\n")
            with body.indent(f"if(!result.{cpp_function}(other))\n"):
                body.write(f'throw pybind11::value_error("Operation failed");\n')
            body.write("return result;\n")
        else:
            body.write(f"return self.{cpp_function}(other);\n")


def wrap_method(
    pyclass: PyClass,
    method: Struct.Method,
    name: str | None = None,
    output: Literal["return", "self"] | Parameter = "return",
    error_handling: Literal["return_false", "none"] = "none",
    copy_self: bool | None = None,
):
    if name is None:
        name = method.name

    if output == "self":
        output_type = pyclass.implementation_name
        if copy_self is None:
            copy_self = True
    elif output == "return":
        output_type = method.return_type
        assert error_handling != "return_false"
    else:
        assert isinstance(output.type, PointerType)
        output_type = output.type.inner

    input_params: list[Parameter] = []
    for param in method.params:
        if method.variadic:
            raise NotImplementedError("Wrapping variadic methods is not supported yet")
        elif param is not output:
            input_params.append(
                Parameter(
                    type=classes.cpp_type_for_wrapper(param.type),
                    name=param.name,
                    default=param.default,
                )
            )

    with pyclass.method(
        output_type, name, *input_params, docstring=method.docstring
    ) as body:
        self_name = "self"
        if copy_self:
            body.write(f"{pyclass.implementation_name} _tmp = {self_name};\n")
            self_name = "_tmp"

        if isinstance(output, Parameter):
            body.write(f"{output_type} {output.name};\n")

        args = ", ".join(
            param.name
            for param in method.params
            if isinstance(param, Parameter) and param.name
        )
        call_expr = f"{self_name}.{method.name}({args})"

        if error_handling == "return_false":
            with body.indent(f"if(!{call_expr})\n"):
                body.write(f'throw pybind11::value_error("Operation failed");\n')
        elif output == "return":
            body.write(f"return {call_expr};\n")
        else:
            body.write(f"{call_expr};\n")

        if output == "self":
            body.write(f"return {self_name};\n")
        elif isinstance(output, Parameter):
            body.write(f"return {output.name};\n")


def auto_wrap_method(pyclass: PyClass, method: Struct.Method, name: str | None = None):
    output = "self" if method.return_type == SimpleType("void") else "return"
    for param in method.params:
        if isinstance(param.type, PointerType) and not param.type.inner.const:
            if isinstance(output, Parameter):
                raise RuntimeError(
                    "auto_wrap_method failed: multiple inferred output parameters"
                )
            output = param
    error_handling = "none"
    if method.return_type == SimpleType("bool"):
        error_handling = "return_false"
        if output == "return":
            output = "self"

    wrap_method(
        pyclass,
        method,
        name=name,
        output=output,
        error_handling=error_handling,
        copy_self=not method.const,
    )


number_mutating_methods_overrides = {
    "raise": "pow",
    "setInterval": None,
    "setToFloatingPoint": None,
    "intervalToPrecision": None,
    "mergeInterval": None,
}

for method in Number.underlying_type.members:
    if not isinstance(method, Struct.Method):
        continue

    if (
        method.const
        or method.return_type != SimpleType(name="bool")
        or method.accessibility != Accessibility.PUBLIC
    ):
        continue

    # These already have Number overloads
    if method.name in {"add", "subtract", "multiply", "divide"}:
        if len(method.params) == 1 and method.params[0].type == SimpleType("long"):
            continue

    # MathOperation is currently not supported and I don't see a reason to support it.
    if any(param.type == SimpleType("MathOperation") for param in method.params):
        continue

    mapped = number_mutating_methods_overrides.get(
        method.name, camel_to_snake(method.name)
    )
    if mapped is None:
        continue

    auto_wrap_method(Number, method, name=mapped)


number_constant_functions = ["e", "pi", "catalan", "euler"]

for constant in number_constant_functions:
    with Number.method(
        "Number",
        constant,
        receiver=None,
        docstring=Number.underlying_type.methods[constant].docstring,
    ) as body:
        body.write("Number result;\n")
        body.write(f"result.{constant}();\n")
        body.write(f"return result;\n")

math_structure_operators = [
    ("*", "__mul__"),
    ("/", "__truediv__"),
    ("+", "__add__"),
    ("-", "__sub__"),
    ("^", "__xor__"),
]

for cpp_op, py_op in math_structure_operators:
    for other_type in ["MathStructure const&", "Number const&"]:
        with MathStructure.method(
            "MathStructureRef", py_op, f"{other_type} other", operator=True
        ) as body:
            body.write("MathStructureRef result = MathStructureRef::construct(self);\n")
            body.write(f"*result {cpp_op}= other;\n")
            body.write("return result;\n")

with MathStructure.method("MathStructureRef", "__neg__", operator=True) as body:
    body.write("return MathStructureRef::adopt(-self);\n")


struct = qalculate_sources.enum("StructureType")
structure_types = []
for variant in struct.members:
    structure_types.append(variant.name.removeprefix("STRUCT_"))
structure_types.remove("ABORTED")

properties_for(
    classes["MathStructure"],
    renames={
        # Remove type-specific checks (use isinstance instead)
        **{f"is{snake_to_pascal(name)}": None for name in structure_types},
        **{f"is{snake_to_pascal(name)}_exp": None for name in structure_types},
        # Type-specific getters
        **{f"{snake_to_camel(name)}": None for name in structure_types},
        **{
            f: None
            for f in (
                "prefix",
                "unit_exp_prefix",
                "isDateTime",
                "find_x_var",
                "isMatrix",
                "symbol",
                "number",
                "function_value",
                "unit_exp_unit",
                "isPlural",
                "last",
                "countChildren",
                "refcount",
                "isAborted",
                "rows",
                "size",
                "type",
                "comparisonType",
            )
        },
    },
)


math_structure_method_whitelist = {
    "differentiate",
    "integrate",
    "expand",
    "isolate_x",
    "simplify",
    "factorize",
    "expandPartialFractions",
    "structure",
}

math_structure_overrides: dict[str, tuple[str | None, str]] = {
    "EvaluationOptions": (
        "PEvaluationOptions",  # overriden type
        "PEvaluationOptions(global_evaluation_options)",  # overriden default value
    ),
    "timeval": (None, "static_cast<struct timeval*>(nullptr)"),
}

for method in MathStructure.underlying_type.methods.values():
    # FIXME: funny workaround (Cannot accept a std::vector* with pybind)
    if method.name in ("integrate", "int"):
        continue

    if method.name not in math_structure_method_whitelist:
        continue

    # Ignore variadic methods
    if method.variadic:
        print(f"warning: ignoring variadic MathStructure method: {method.params}")
        continue

    exposed_params = []
    for param in method.params:
        name = param.name
        type = param.type
        default = param.default

        cast_default = True
        for patterns, override in math_structure_overrides.items():
            type_str = str(type)
            if patterns in type_str:
                if override[0] is None:
                    name = None
                else:
                    type = Type.parse(type_str.replace(patterns, override[0]))
                default = override[1]
                cast_default = False
                break

        if cast_default and param.default:
            default = f"static_cast<{type}>({param.default})"

        exposed_params.append(Parameter(type, name, default))

    args = ", ".join(
        f"{param.name}" if param.name else param.default for param in exposed_params
    )

    with MathStructure.method(
        "QalcRef<MathStructure>",
        camel_to_snake(method.name),
        *(param for param in exposed_params if param.name),
        docstring=method.docstring,
    ) as body:
        body.write("MathStructureRef result = MathStructureRef::construct(self);\n")
        if method.return_type == SimpleType("bool"):
            body.write(f"if(!result->{method.name}({args})) return nullptr;\n")
        else:
            raise RuntimeError(
                f"Mutating MathStructure method return type {method.return_type} handling not implemented"
            )
        body.write("return result;\n")

impl.write('#include "proxies.hh"\n')

with function_declaration(
    "void MathStructure_repr(MathStructure const *mstruct, std::string &output)"
):
    impl.write("switch(mstruct->type()) {\n")
    for name in structure_types:
        with impl.indent(f"case STRUCT_{name}:\n"):
            class_ = f"MathStructure{snake_to_pascal(name)}Proxy"
            impl.write(f"(({class_} const*)mstruct)->repr(output);\n")
            impl.write(f"break;\n")
    with impl.indent("default:\n"):
        impl.write(
            'throw std::runtime_error("Cannot stringify unknown math structure type " + std::to_string(mstruct->type()));\n'
        )
        impl.write("break;\n")
    impl.write("}\n")

with function_declaration(
    f"{MATH_STRUCTURE_CLASS}& add_math_structure_proxies({MATH_STRUCTURE_CLASS}& class_)"
):
    for name in structure_types:
        class_ = f"MathStructure{snake_to_pascal(name)}Proxy"
        python_name = snake_to_pascal(name)
        if python_name == "Datetime":
            python_name = "DateTime"
        impl.write(
            f'qalc_class_<{class_}, {class_}::Base> {name.lower()}(class_, "{python_name}", py::is_final{{}});\n'
        )
        impl.write(f"{class_}::init({name.lower()});\n")

    impl.write("return class_;\n")


with output_directory.writer("mathstructure_type_hook.cc") as writer:
    writer = IndentedWriter(writer)
    writer.write("#include <pybind11/pybind11.h>\n")
    writer.write("#include <libqalculate/MathStructure.h>\n")
    writer.write('#include "proxies.hh"\n')
    writer.write("\n")
    writer.write("namespace PYBIND11_NAMESPACE {\n")

    with writer.indent(
        "void const *polymorphic_type_hook<MathStructure>::get(MathStructure const *src, std::type_info const *&type) {\n"
    ):
        writer.write("if(src == nullptr) return nullptr;\n")
        writer.write("switch(src->type()) {\n")
        for name in structure_types:
            class_ = f"MathStructure{snake_to_pascal(name)}Proxy"
            with writer.indent(f"case STRUCT_{name}:\n"):
                writer.write(f"type = &typeid({class_});\n")
                writer.write(f"return static_cast<{class_} const *>(src);\n")
        with writer.indent(f"default:\n"):
            writer.write(
                'throw std::runtime_error("No proxy object for MathStructure type " + std::to_string(src->type()));\n'
            )
        writer.write("}\n")
    writer.write("};\n}\n")

options(
    classes["ExpressionName"],
    exclude={"priv"},
    define_new_default=True,
    pass_by_type={"std::string": "std::string_view"},
)

properties_for(
    classes["ExpressionItem"],
    renames={
        "refcount": None,
        "type": None,
        "subtype": None,
        "id": None,
        "countNames": None,
    },
)

BUILTIN_FUNCTION_REGEX = re.compile(
    "^DECLARE_BUILTIN_FUNCTION.*?\\(([a-zA-Z_]+),\\s+([a-zA-Z_]+)\\)", re.MULTILINE
)

for match in BUILTIN_FUNCTION_REGEX.finditer(
    qalculate_sources.get("BuiltinFunctions.h").text
):
    name, id = match.groups()
    classes.add(
        name,
        holder=f"QalcRef<{name}>",
        bases=["MathFunction"],
    )

properties_for(
    classes["Assumptions"],
    allow_readwrite=True,
    require_getter_const=False,
    add_repr_from_rw=True,
)

properties_for(
    classes["Unit"],
    allow_readwrite=True,
    add_repr_from_rw=True,
    renames={
        "copy": None,
        "type": None,
        "subtype": None,
        "isSIUnit": None,
        "system": None,
        # TODO: What do these do??
        "convertToBaseUnit": None,
        "convertFromBaseUnit": None,
    },
    extra_for_repr=["is_si", "system"],
)

extra_includes: list[tuple[Iterable[str], list[str]]] = [
    ("Options", ['"options.hh"']),
    ("Assumptions", ['"wrappers.hh"']),
    ("Number", ["<pybind11/stl.h>"]),
    (
        ("MathStructure", "MathFunction", "Unit", "ExpressionItem"),
        ['"ref.hh"', '"options.hh"'],
    ),
]

add_mode = {
    "ExpressionName",
    "SortOptions",
    "PrintOptions",
    "ParseOptions",
    "EvaluationOptions",
}
builtin_function_classes: list[PyClass] = []
for pyclass in classes:
    if pyclass.name.endswith("Function") and pyclass.name != "MathFunction":
        builtin_function_classes.append(pyclass)
    else:
        mode = "create" if pyclass.name in add_mode else "modify"
        name = "add_" if mode == "create" else "init_"
        name += "auto_"
        name += pascal_to_snake(pyclass.name)
        with output_directory.writer(f"classes/{pyclass.name}.cc") as file:
            includes = []
            for patterns, extra in extra_includes:
                if isinstance(patterns, str):
                    patterns = [patterns]
                if any(True for pattern in patterns if pattern in pyclass.name):
                    includes += extra

            writer = prepare_impl_file(
                file,
                includes,
            )

            if pyclass in class_extra_impl:
                writer.write(class_extra_impl[pyclass])

            pyclass.write_init_function(
                name,
                header,
                writer,
                mode=mode,
            )

    pyclass.write_types(typings, classes)

with function_declaration("void add_builtin_functions(pybind11::module_ &m)"):
    for pyclass in builtin_function_classes:
        impl.write("(void)")
        pyclass.write_pyclass_expression(impl, "m")
        impl.write(";\n")


header.close()
impl.close()


assert isinstance(typings._inner, StringIO)
types_output.write_text(
    merge_typing_files(
        typings._inner.getvalue(),
        Path(__file__).parent.parent / "src" / "types.pyi",
        classes
    )
)

output_directory.close()
