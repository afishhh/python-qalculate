from pathlib import Path
import string
import re
from contextlib import contextmanager
import sys

from .parsing import (
    Accessibility,
    ParsedSourceFiles,
    SimpleType,
    Struct,
)
from .utils import *

libqalculate_src = Path(sys.argv[1]) / "libqalculate"
output_directory = Path(sys.argv[2])
qalculate_sources = ParsedSourceFiles(libqalculate_src.glob("*.h"))

MATH_STRUCTURE_CLASS = "qalc_class_<MathStructure>"

output_directory.mkdir(exist_ok=True)
header = IndentedWriter((output_directory / "generated.hh").open("w+"))
impl = IndentedWriter((output_directory / "generated.cc").open("w+"))

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
    name: str,
    *,
    allow_readwrite: bool = False,
    require_getter_const: bool = True,
    renames: dict[str, str | None] = {},
    pybind_class: str | None = None,
    add_repr_from_rw: bool = False,
):
    class_type = f"pybind11::class_<{name}>" if not pybind_class else pybind_class

    struct = qalculate_sources.structure(name)
    with function_declaration(
        f"{class_type} &add_{pascal_to_snake(name)}_properties({class_type} &class_)"
    ):
        with impl.indent("return class_\n"):
            added_rw_props = []

            for member in iter_properties(
                struct, require_getter_const=require_getter_const
            ):
                mapped = renames.get(member.name, camel_to_snake(member.name))
                if mapped is None:
                    continue

                setter = struct.methods.get(f"set{camel_to_pascal(member.name)}", None)
                if setter and len(setter.params) == 1 and allow_readwrite:
                    impl.write(
                        f'.def_property("{mapped}", &{name}::{member.name}, &{name}::{setter.name})\n'
                    )

                    added_rw_props.append(mapped)
                else:
                    impl.write(
                        f'.def_property_readonly("{mapped}", &{name}::{member.name})\n'
                    )

            if add_repr_from_rw:
                define_repr(name, added_rw_props)
        impl.write(";\n")


def define_repr(
    name: str,
    properties: Iterable[str],
):
    with impl.indent(f'.def("__repr__", [](py::object s) {{\n'):
        impl.write(f'std::string output = "{name}(";\n')
        impl.write(f"output.reserve(512);\n")
        for i, name in enumerate(properties):
            if i != 0:
                impl.write(f'output += ", ";\n')
            impl.write(f'output += "{name}=";\n')
            impl.write(
                f'output += s.attr("{name}").attr("__repr__")().cast<std::string_view>();\n'
            )
        impl.write("return output;\n")
    impl.write("})\n")


def options(
    name: str,
    *,
    exclude: set[str] = set(),
    override_class=None,
    func_name=None,
    define_new_default=False,
    pass_by_type: dict[str, str] = {},
):
    if func_name is None:
        func_name = f"add_{pascal_to_snake(name)}"

    defaults_name = f"default_{pascal_to_snake(name)}"

    if define_new_default:
        defaults_name = f"_autogen_{pascal_to_snake(name)}_defaults"
        impl.write(f"{name} {defaults_name};\n")

    pybind_class = f"pybind11::class_<{override_class or name}>"
    struct = qalculate_sources.structure(name)

    with function_declaration(f"{pybind_class} {func_name}(pybind11::module_ &m)"):
        with impl.indent(f'return {pybind_class}(m, "{name}")\n'):
            options = {}
            for field in struct.fields.values():
                if field.accessibility != Accessibility.PUBLIC:
                    continue

                if field.name in exclude:
                    continue

                impl.write(
                    f'.def_readwrite("{camel_to_snake(field.name)}", &{name}::{field.name})\n'
                )

                options[field.name] = field.type

            impl.write(".def(py::init([](")
            options = list(options.items())
            for i, (field, type) in enumerate(options):
                if i > 0:
                    impl.write(", ")
                impl.write(f"{pass_by_type.get(type, type)} {field}")
            with impl.indent(") {\n"):
                impl.write(f"{name} result;\n")
                for field, type in options:
                    impl.write(f"result.{field} = {field};\n")
                impl.write(f"return result;\n")
            impl.write("}), py::kw_only{}")
            for field, type in options:
                impl.write(f', py::arg("{field}") = {defaults_name}.{field}')
            impl.write(")\n")

            define_repr(name, (n for n, _ in options))
        impl.write(";\n")


enums: list[str] = []


def enum(name: str, prefix: str | None = None):
    enums.append(name)
    enum = qalculate_sources.enum(name)
    if prefix is None:
        prefix = f"{pascal_to_snake(name).upper()}_"

    with function_declaration(
        f"pybind11::enum_<{name}> add_{pascal_to_snake(name)}_enum(pybind11::module_ &m)"
    ):
        with impl.indent(f'return pybind11::enum_<{name}>(m, "{name}")\n'):
            for variant in enum.members:
                doc_arg = (
                    (
                        ', "'
                        + variant.docstring.replace('"', '\\"').replace("\n", "\\n")
                        + '"'
                    )
                    if variant.docstring
                    else ""
                )
                impl.write(
                    f'.value("{variant.name.removeprefix(prefix)}", {name}::{variant.name}{doc_arg})\n'
                )
        impl.write(";\n")


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

options("SortOptions")
options(
    "PrintOptions",
    exclude={
        "prefix",
        "is_approximate",
        "can_display_unicode_string_arg",
        "can_display_unicode_string_function",
    },
)
options("ParseOptions", exclude={"unended_function", "default_dataset"})
options(
    "EvaluationOptions",
    exclude={"isolate_var", "protected_function"},
    override_class="class PEvaluationOptions",
)


properties_for(
    "Number",
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

struct = qalculate_sources.enum("StructureType")
structure_types = []
for variant in struct.members:
    structure_types.append(variant.name.removeprefix("STRUCT_"))
structure_types.remove("ABORTED")

properties_for(
    "MathStructure",
    renames={
        # Remove type-specific checks (use isinstance instead)
        **{f"is{snake_to_pascal(name)}": None for name in structure_types},
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
    pybind_class="qalc_class_<MathStructure>",
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

math_structure_overrides = {
    "EvaluationOptions": (
        "PEvaluationOptions",  # overriden type
        "PEvaluationOptions(default_evaluation_options)",  # overriden default value
    ),
    "timeval": (None, "static_cast<struct timeval*>(nullptr)"),
}

with function_declaration(
    f"{MATH_STRUCTURE_CLASS} &add_math_structure_methods({MATH_STRUCTURE_CLASS} &class_)"
):
    struct = qalculate_sources.structure("MathStructure")
    with impl.indent("return class_\n"):
        for method in struct.methods.values():
            # FIXME: funny workaround (Cannot accept a std::vector* with pybind)
            if method.name in ("integrate", "int"):
                continue

            if method.name not in math_structure_method_whitelist:
                continue

            # Ignore variadic methods (FIXME: for now?)
            if "..." in method.params:
                continue

            exposed_params = []
            for param in method.params:
                assert param != "..."

                name = param.name
                type = str(param.type)
                default = param.default

                cast_default = True
                for pattern, override in math_structure_overrides.items():
                    if pattern in type:
                        if override[0] is None:
                            name = None
                        else:
                            type = type.replace(pattern, override[0])
                        default = override[1]
                        cast_default = False
                        break

                if cast_default and param.default:
                    default = f"static_cast<{type}>({param.default})"

                exposed_params.append((type, name, default))

            params_no_defaults = ", ".join(
                f"{type} {name}"
                for type, name, _, in exposed_params
                if name is not None
            )
            args = ", ".join(
                f"{name}" if name else default for _, name, default in exposed_params
            )

            with impl.indent(
                f'.def("{camel_to_snake(method.name)}", [](MathStructure const& self, {params_no_defaults}) -> MathStructureRef {{\n'
            ):
                impl.write(
                    "MathStructureRef result = MathStructureRef::construct(self);\n"
                )
                if method.return_type == SimpleType("bool"):
                    impl.write(f"if(!result->{method.name}({args})) return nullptr;\n")
                else:
                    raise RuntimeError(
                        f"Mutating MathStructure method return type {method.return_type} handling not implemented"
                    )
                impl.write("return result;\n")
            impl.write("}")

            for type, name, default in exposed_params:
                if name is None:
                    continue

                impl.write(f', py::arg("{name}")')
                if default is not None:
                    impl.write(f" = {default}")
            impl.write(")\n")
    impl.write(";\n")

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
    ("==", "__eq__"),
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
    with impl.indent("switch(mstruct->type()) {\n"):
        for name in structure_types:
            impl.write(f"case STRUCT_{name}:\n")
            class_ = f"MathStructure{snake_to_pascal(name)}Proxy"
            impl.write(f"(({class_} const*)mstruct)->repr(output);\n")
            impl.write(f"break;\n")
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
    "ExpressionName",
    exclude={"priv"},
    func_name="add_expression_name_auto",
    define_new_default=True,
    pass_by_type={"std::string": "std::string_view"},
)

properties_for(
    "ExpressionItem",
    renames={
        "refcount": None,
        "type": None,
        "subtype": None,
        "id": None,
        "countNames": None,
    },
    pybind_class="qalc_class_<ExpressionItem>",
)

BUILTIN_FUNCTION_REGEX = re.compile(
    "^DECLARE_BUILTIN_FUNCTION.*?\\(([a-zA-Z_]+),\\s+([a-zA-Z_]+)\\)", re.MULTILINE
)

with function_declaration("void add_builtin_functions(py::module_ &m)"):
    for match in BUILTIN_FUNCTION_REGEX.finditer(
        qalculate_sources.get("BuiltinFunctions.h").text
    ):
        name, id = match.groups()
        impl.write(f'(void)qalc_class_<{name}, MathFunction>(m, "{name}");\n')

properties_for(
    "Assumptions",
    allow_readwrite=True,
    require_getter_const=False,
    pybind_class="pybind11::class_<class PAssumptions>",
    add_repr_from_rw=True,
)

header.close()
impl.close()
