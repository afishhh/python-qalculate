from pathlib import Path
import re
from contextlib import contextmanager
import sys

from generate.bindings import KW_ONLY, PyClass

from .parsing import (
    Accessibility,
    Parameter,
    ParsedSourceFiles,
    SimpleType,
    Struct,
    Type,
)
from .utils import *

libqalculate_src = Path(sys.argv[1]) / "libqalculate"
output_directory = Path(sys.argv[2])
qalculate_sources = ParsedSourceFiles(libqalculate_src.glob("*.h"))

MATH_STRUCTURE_CLASS = "qalc_class_<MathStructure>"

output_directory.mkdir(exist_ok=True)
header = IndentedWriter((output_directory / "generated.hh").open("w+"))
impl = IndentedWriter((output_directory / "generated.cc").open("w+"))
typings = IndentedWriter((output_directory / "types.pyi").open("w+"))

typings.write("import typing\n")

classes = {
    "MathStructure": PyClass(
        "MathStructure", extra=["QalcRef<MathStructure>"], sources=qalculate_sources
    ),
    "ExpressionItem": PyClass(
        "ExpressionItem", extra=["QalcRef<ExpressionItem>"], sources=qalculate_sources
    ),
    "ExpressionName": PyClass("ExpressionName", sources=qalculate_sources),
    "Assumptions": PyClass(
        "Assumptions", wrapper="class PAssumptions", sources=qalculate_sources
    ),
    "Unit": PyClass(
        "Unit",
        extra=["QalcRef<Unit>"],
        bases=["ExpressionItem"],
        sources=qalculate_sources,
    ),
    "EvaluationOptions": PyClass(
        "EvaluationOptions",
        wrapper="class PEvaluationOptions",
        sources=qalculate_sources,
    ),
    "MathFunction": PyClass(
        "MathFunction",
        extra=["QalcRef<MathFunction>"],
        bases=["ExpressionItem"],
        sources=qalculate_sources,
    ),
}

for simple_class in ("Number", "SortOptions", "PrintOptions", "ParseOptions"):
    classes[simple_class] = PyClass(simple_class, sources=qalculate_sources)

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
def function_declaration(signature: str):
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
            assert setter.params[0] != "..."
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
        defaults_name = f"_autogen_{pascal_to_snake(pyclass.name)}_defaults"
        impl.write(f"{pyclass.name} {defaults_name};\n")

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


def enum(name: str, prefix: str | None = None):
    enums.append(name)
    enum = qalculate_sources.enum(name)
    if prefix is None:
        prefix = f"{pascal_to_snake(name).upper()}_"

    typings.indent(f"class {name}:\n")

    with function_declaration(
        f"pybind11::enum_<{name}> add_{pascal_to_snake(name)}_enum(pybind11::module_ &m)"
    ):
        with impl.indent(f'return pybind11::enum_<{name}>(m, "{name}")\n'):
            for variant in enum.members:
                docarg = (
                    f", {cpp_string(variant.docstring)}" if variant.docstring else ""
                )
                pyvariant = variant.name.removeprefix(prefix)
                impl.write(f'.value("{pyvariant}", {name}::{variant.name}{docarg})\n')
                typings.write(f"{pyvariant}: typing.ClassVar[{name}]\n")
        impl.write(";\n")

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


enum("ApproximationMode", "APPROXIMATION_")
enum("NumberFractionFormat", "FRACTION_")
enum("StructuringMode", "STRUCTURING_")
enum("AutoPostConversion", "POST_CONVERSION_")
enum("ComparisonType", "COMPARISON_")
enum("RoundingMode", "ROUNDING_")
enum("MessageType", "MESSAGE_")
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
    enum(name)
enum("AutomaticFractionFormat", "AUTOMATIC_FRACTION_")
enum("AutomaticApproximation", "AUTOMATIC_APPROXIMATION_")

# This one is initialized manually (to add helper properties)
enums.remove("ComparisonResult")
with function_declaration("void add_all_enums(pybind11::module_ &m)"):
    for enm in enums:
        impl.write(f"add_{pascal_to_snake(enm)}_enum(m);\n")

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
    ("multiply", "__mul__"),
    ("divide", "__truediv__"),
    ("add", "__add__"),
    ("subtract", "__sub__"),
    ("bitXor", "__xor__"),
]

with function_declaration(
    f"py::class_<Number> &add_number_operators(py::class_<Number> &class_)"
):
    with impl.indent("return class_\n"):
        for qalc_function, operator in number_operators:
            with impl.indent(
                f'.def("{operator}", [](Number const &self, Number const &other) {{\n'
            ):
                impl.write(f"Number result = self;\n")
                with impl.indent(f"if(!result.{qalc_function}(other))\n"):
                    impl.write(f'throw py::value_error("Operation failed");\n')
                impl.write("return result;\n")
            impl.write("}, py::is_operator{})\n")
        impl.write(";\n")


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

MathStructure = classes["MathStructure"]
for method in MathStructure.underlying_type.methods.values():
    # FIXME: funny workaround (Cannot accept a std::vector* with pybind)
    if method.name in ("integrate", "int"):
        continue

    if method.name not in math_structure_method_whitelist:
        continue

    # Ignore variadic methods
    if "..." in method.params:
        print(f"warning: ignoring variadic MathStructure method: {method.params}")
        continue

    exposed_params = []
    for param in method.params:
        assert param != "..."

        name = param.name
        type = param.type
        default = param.default

        cast_default = True
        for pattern, override in math_structure_overrides.items():
            type_str = str(type)
            if pattern in type_str:
                if override[0] is None:
                    name = None
                else:
                    type = Type.parse(type_str.replace(pattern, override[0]))
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
    ) as body:
        body.write("MathStructureRef result = MathStructureRef::construct(self);\n")
        if method.return_type == SimpleType("bool"):
            body.write(f"if(!result->{method.name}({args})) return nullptr;\n")
        else:
            raise RuntimeError(
                f"Mutating MathStructure method return type {method.return_type} handling not implemented"
            )
        body.write("return result;\n")

math_structure_operators = [
    ("*", "__mul__"),
    ("*=", "__imul__"),
    ("/", "__truediv__"),
    ("/=", "__itruediv__"),
    ("+", "__add__"),
    ("+=", "__iadd__"),
    ("-", "__sub__"),
    ("-=", "__isub__"),
    ("^", "__xor__"),
    ("^=", "__ixor__"),
]

with function_declaration(
    f"{MATH_STRUCTURE_CLASS} &add_math_structure_operators({MATH_STRUCTURE_CLASS} &class_)"
):
    with impl.indent("return class_"):
        for cpp_op, py_op in math_structure_operators:
            # Non-copying operator
            if cpp_op.endswith("="):
                for other_type in ["Number", "std::string"]:
                    impl.write(f".def(py::self {cpp_op} {other_type}())\n")
                impl.write(f".def(py::self {cpp_op} py::self)\n")
            else:
                for other_type in ["MathStructure", "Number", "std::string"]:
                    with impl.indent(
                        f'.def("{py_op}", [](MathStructure const &self, {other_type} const &other) {{\n'
                    ):
                        impl.write(
                            "MathStructureRef result = MathStructureRef::construct(self);\n"
                        )
                        impl.write(f"*result {cpp_op}= other;\n")
                        impl.write("return result;\n")
                    impl.write("}, py::is_operator{})\n")

        with impl.indent(f'.def("__neg__", [](MathStructure const &self) {{\n'):
            impl.write("return MathStructureRef::adopt(-self);\n")
        impl.write("}, py::is_operator{})\n")
    impl.write(";\n")

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
        impl.write(
            f'qalc_class_<{class_}, {class_}::Base> {name.lower()}(class_, "{snake_to_pascal(name)}", py::is_final{{}});\n'
        )
        impl.write(f"{class_}::init({name.lower()});\n")

    impl.write("return class_;\n")


header.write("namespace PYBIND11_NAMESPACE {\n")
with header.indent("template <> struct polymorphic_type_hook<MathStructure> {\n"):
    with header.indent(
        "static void const *get(MathStructure const *src, std::type_info const *&type) {\n"
    ):
        header.write("if(src == nullptr) return nullptr;\n")
        header.write("switch(src->type()) {\n")
        for name in structure_types:
            class_ = f"MathStructure{snake_to_pascal(name)}Proxy"
            with header.indent(f"case STRUCT_{name}:\n"):
                header.write(f"type = &typeid({class_});\n")
                header.write(f"return static_cast<{class_} const *>(src);\n")
        with header.indent(f"default:\n"):
            header.write(
                'throw std::runtime_error("No proxy object for MathStructure type " + std::to_string(src->type()));\n'
            )
        header.write("}\n")
    header.write("}\n")
header.write("};\n}\n")

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
    classes[name] = PyClass(
        name,
        extra=[f"QalcRef<{name}>"],
        bases=["MathFunction"],
        sources=qalculate_sources,
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

add_mode = {
    "ExpressionName",
    "SortOptions",
    "PrintOptions",
    "ParseOptions",
    "EvaluationOptions",
}
builtin_function_classes: list[PyClass] = []
for pyclass in classes.values():
    if pyclass.name.endswith("Function"):
        builtin_function_classes.append(pyclass)
    else:
        mode = "create" if pyclass.name in add_mode else "modify"
        name = "add_" if mode == "create" else "init_"
        name += "auto_"
        name += pascal_to_snake(pyclass.name)
        pyclass.write_init_function(name, header, impl, mode=mode)
    pyclass.write_types(typings)

with function_declaration("void add_builtin_functions(pybind11::module_ &m)"):
    for pyclass in builtin_function_classes:
        impl.write("(void)")
        pyclass.write_pyclass_expression(impl, "m")
        impl.write(";\n")


header.close()
impl.close()
