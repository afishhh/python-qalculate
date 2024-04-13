from pathlib import Path
import string
import re
from contextlib import contextmanager
import sys

from .parsing import Accessibility, ParsedSourceFiles, SimpleType, Struct
from .utils import *
# from .debug_utils import pprint_structure

libqalculate_src = Path(sys.argv[1]) / "libqalculate"
output_directory = Path(sys.argv[2])
qalculate_sources = ParsedSourceFiles(libqalculate_src.glob("*.h"))

MATH_STRUCTURE_CLASS = "qalc_class_<MathStructure>"

# pprint_structure(qalculate_sources.structure("ExpressionName"))
# pprint_structure(qalculate_sources.structure("MathStructure"))
# pprint_structure(qalculate_sources.structure("PrintOptions"))


def clean(text: str) -> str:
    text = re.sub("/\\*[^*].*?\\*/", "", text, flags=re.MULTILINE | re.DOTALL)
    text = re.sub("[^/]// .*$", "", text, flags=re.MULTILINE)
    text = "\n".join(line for line in text.splitlines() if line.strip())
    return text


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


def process_simple_properties(
    name: str, text: str, renames: dict[str, str | None] = {}, qalc_class: bool = False
):
    PROPERTY_REGEX = re.compile(
        "(virtual\\s+)?(const\\s+)?([a-zA-Z_::]+)[ &]+([a-zA-Z_]+)\\(\\) const;"
    )

    class_type = (
        f"pybind11::class_<{name}>" if not qalc_class else f"qalc_class_<{name}>"
    )

    with function_declaration(
        f"{class_type} &add_{pascal_to_snake(name)}_properties({class_type} &class_)"
    ):
        with impl.indent("return class_\n"):
            for line in text.splitlines()[1:-1]:
                if match := PROPERTY_REGEX.match(line.strip()):
                    _, _, _, prop = match.groups()
                    mapped = renames.get(prop, camel_to_snake(prop))
                    if mapped is None:
                        continue
                    impl.write(f'.def_property_readonly("{mapped}", &{name}::{prop})\n')
        impl.write(";\n")


def process_options_declaration(
    name: str,
    struct: Struct,
    exclude: set[str],
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

            with impl.indent(f'.def("__repr__", [](py::object s) {{\n'):
                impl.write(f'std::string output = "{name}(";\n')
                impl.write(f"output.reserve(512);\n")
                for i, (field, type) in enumerate(options):
                    if i != 0:
                        impl.write(f'output += ", ";\n')
                    impl.write(f'output += "{field}=";\n')
                    impl.write(
                        f'output += s.attr("{field}").attr("__repr__")().cast<std::string_view>();\n'
                    )
                impl.write("return output;\n")
            impl.write("})\n")
        impl.write(";\n")


def process_enum_declaration(name: str, text: str, prefix: str):
    declarations = text.splitlines()[1:-1]

    with function_declaration(
        f"pybind11::enum_<{name}> add_{pascal_to_snake(name)}_enum(pybind11::module_ &m)"
    ):
        with impl.indent(f'return pybind11::enum_<{name}>(m, "{name}")\n'):
            doc_comment = None
            for line in declarations:
                line = line.strip()
                if line.startswith("//"):
                    if doc_comment is None:
                        doc_comment = ""
                    else:
                        doc_comment += "\n"
                    doc_comment += line.removeprefix("///").strip()
                else:
                    value = line.removesuffix(",")
                    doc_arg = (
                        (', "' + doc_comment.replace('"', '\\"') + '"')
                        if doc_comment is not None
                        else ""
                    )
                    impl.write(
                        f'.value("{value.removeprefix(prefix)}", {name}::{value}{doc_arg})\n'
                    )
                    doc_comment = None
        impl.write(";\n")


enums: list[str] = []


def enum(name: str, prefix: str | None = None):
    enums.append(name)
    if prefix is None:
        prefix = f"{pascal_to_snake(name).upper()}_"
    declaration = qalculate_sources.enum(name)
    return process_enum_declaration(name, declaration.block, prefix)


def options(name: str, exclude: set[str] = set(), **kwargs):
    declaration = qalculate_sources.structure(name)
    return process_options_declaration(name, declaration, exclude, **kwargs)


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
):
    enum(name)
enum("AutomaticFractionFormat", "AUTOMATIC_FRACTION_")
enum("AutomaticApproximation", "AUTOMATIC_APPROXIMATION_")

# This one is initialized manually (to add helper properties)
enums.remove("ComparisonResult")
with function_declaration("void add_all_enums(pybind11::module_ &m)"):
    for enm in enums:
        impl.write(f"add_{pascal_to_snake(enm)}_enum(m);\n")

impl.write('#include "options.hh"\n')

options("SortOptions")
options(
    "PrintOptions",
    {
        "prefix",
        "is_approximate",
        "can_display_unicode_string_arg",
        "can_display_unicode_string_function",
    },
)
options("ParseOptions", {"unended_function", "default_dataset"})
options(
    "EvaluationOptions",
    {"isolate_var", "protected_function"},
    override_class="class PEvaluationOptions",
)


def properties_for(
    name: str, renames: dict[str, str | None] = {}, qalc_class: bool = False
):
    declaration = qalculate_sources.structure(name)
    process_simple_properties(name, declaration.block, renames, qalc_class)


properties_for(
    "Number",
    {
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
for line in struct.block.splitlines()[1:-1]:
    line = line.strip().removesuffix(",")
    if all(c in string.ascii_letters + string.digits + "_" for c in line):
        name = line.removeprefix("STRUCT_")
        structure_types.append(name)
structure_types.remove("ABORTED")

properties_for(
    "MathStructure",
    {
        # Remove type-specific checks (use isinstance instead)
        **{f"is{snake_to_pascal(name)}": None for name in structure_types},
        **{
            f: None
            for f in (
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
    qalc_class=True,
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

METHOD_REGEX = re.compile("([a-zA-Z_]+)\\s+([a-zA-Z_]+)\\((.*?)\\)\\s*(const)?;")

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

struct = qalculate_sources.structure("ExpressionName")
process_options_declaration(
    "ExpressionName",
    struct,
    {"priv"},
    func_name="add_expression_name_auto",
    define_new_default=True,
    pass_by_type={"std::string": "std::string_view"},
)

properties_for(
    "ExpressionItem",
    {"refcount": None, "type": None, "subtype": None, "id": None, "countNames": None},
    qalc_class=True,
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

header.close()
impl.close()
