from pathlib import Path
import string
import re
from contextlib import contextmanager
import sys
from .utils import IndentedWriter

libqalculate_src = Path(sys.argv[1]) / "libqalculate"
output_directory = Path(sys.argv[2])
output_directory.mkdir(exist_ok=True)

includes_h = (libqalculate_src / "includes.h").read_text()
number_h = (libqalculate_src / "Number.h").read_text()
calculator_h = (libqalculate_src / "Calculator.h").read_text()
math_structure_h = (libqalculate_src / "MathStructure.h").read_text()
expression_item_h = (libqalculate_src / "ExpressionItem.h").read_text()
builtin_functions_h = (libqalculate_src / "BuiltinFunctions.h").read_text()

MATH_STRUCTURE_CLASS = "qalc_class_<MathStructure>"


def camel_to_snake(name: str):
    def find_any(chars: str):
        for i, c in enumerate(name):
            if c in chars:
                return i
        return -1

    while (i := find_any(string.ascii_uppercase)) != -1:
        name = name[:i] + "_" + name[i].lower() + name[i + 1 :]
    return name


def pascal_to_snake(name: str):
    name = name[0].lower() + name[1:]
    return camel_to_snake(name)


def snake_to_pascal(name: str):
    return "".join(part.capitalize() for part in name.split("_"))


def snake_to_camel(name: str):
    name = snake_to_pascal(name)
    name = name[0].lower() + name[1:]
    return name


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


def find_end_of_block(text: str, start: int = 0, level: int = 0) -> int:
    it = enumerate(text[start:])
    for i, c in it:
        if c == "}":
            if level == 0:
                return i + start
            level -= 1
        elif c == "{":
            level += 1
    return -1


def extract_declaration(keyword: str, name: str, text: str):
    start = text.find(f"{keyword} {name} {{")
    if start == -1:
        start = 0
        while (start := text.find(f"typedef {keyword} {{", start)) != -1:
            end = find_end_of_block(text, start, -1)
            if text[end:].split(maxsplit=2)[1].removesuffix(";") == name:
                return text[start : end + 1]
            start += 1

        return None
    end = find_end_of_block(text, start, -1)
    return text[start : end + 1]


def process_options_declaration(
    name: str,
    text: str,
    exclude: set[str],
    override_class=None,
    func_name=None,
    define_new_default=False,
    pass_by_type: dict[str, str] = {},
):
    declarations = text.splitlines()[1:-1]
    field_regex = re.compile("([a-zA-Z_::]+)\\s+([a-zA-Z_]+);")

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
            for line in declarations:
                if match := field_regex.match(line.strip()):
                    type, field = match.groups()
                    if field in exclude:
                        continue
                    impl.write(
                        f'.def_readwrite("{camel_to_snake(field)}", &{name}::{field})\n'
                    )
                    options[field] = type

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


def enum(name: str, prefix: str | None = None, text=includes_h):
    enums.append(name)
    if prefix is None:
        prefix = f"{pascal_to_snake(name).upper()}_"
    declaration = extract_declaration("enum", name, text)
    assert declaration is not None

    return process_enum_declaration(name, declaration, prefix)


def options(name: str, exclude: set[str] = set(), **kwargs):
    declaration = extract_declaration("struct", name, includes_h)
    assert declaration is not None
    return process_options_declaration(name, declaration, exclude, **kwargs)


enum("ApproximationMode", "APPROXIMATION_")
enum("NumberFractionFormat", "FRACTION_")
enum("StructuringMode", "STRUCTURING_")
enum("AutoPostConversion", "POST_CONVERSION_")
enum("ComparisonType", "COMPARISON_")
enum("RoundingMode", "ROUNDING_")
enum("MessageType", "MESSAGE_", calculator_h)
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
enum("AutomaticFractionFormat", "AUTOMATIC_FRACTION_", calculator_h)
enum("AutomaticApproximation", "AUTOMATIC_APPROXIMATION_", calculator_h)

# This one is initialized manually (to add helper properties)
enums.remove("ComparisonResult")
with function_declaration("void add_all_enums(pybind11::module_ &m)"):
    for enm in enums:
        impl.write(f"add_{pascal_to_snake(enm)}_enum(m);\n")

impl.write('#include "options.hh"\n')

options("SortOptions")
options("PrintOptions")
options("ParseOptions", {"unended_function", "default_dataset"})
options("EvaluationOptions", override_class="class PEvaluationOptions")


def properties_for(
    name: str, text: str, renames: dict[str, str | None] = {}, qalc_class: bool = False
):
    declaration = extract_declaration("class", name, text)
    assert declaration is not None
    process_simple_properties(name, declaration, renames, qalc_class)


properties_for(
    "Number",
    number_h,
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

declaration = extract_declaration("enum", "StructureType", math_structure_h)
assert declaration is not None
structure_types = []
for line in declaration.splitlines()[1:-1]:
    line = line.strip().removesuffix(",")
    if all(c in string.ascii_letters + string.digits + "_" for c in line):
        name = line.removeprefix("STRUCT_")
        structure_types.append(name)
structure_types.remove("ABORTED")

properties_for(
    "MathStructure",
    math_structure_h,
    {
        # Remove type-specific checks (use instanceof instead)
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


math_structure_mutating_methods = {
    **{
        x: camel_to_snake(x)
        for x in (
            "differentiate",
            "integrate",
            "expand",
            "isolate_x",
            "simplify",
            "factorize",
            "expandPartialFractions",
            "structure",
        )
    }
}

math_structure_overrides = {
    "EvaluationOptions": (
        "PEvaluationOptions",
        "PEvaluationOptions(default_evaluation_options)",
        False,
    ),
    "struct timeval": (None, "nullptr", True),
}

METHOD_REGEX = re.compile("([a-zA-Z_]+)\\s+([a-zA-Z_]+)\\((.*?)\\)\\s*(const)?;")

with function_declaration(
    f"{MATH_STRUCTURE_CLASS} &add_math_structure_methods({MATH_STRUCTURE_CLASS} &class_)"
):
    declaration = extract_declaration("class", "MathStructure", math_structure_h)
    assert declaration is not None
    with impl.indent("return class_\n"):
        for line in declaration.splitlines()[1:-1]:
            if match := METHOD_REGEX.match(line.strip()):
                ret, method, params, _ = match.groups()
                # FIXME: funny workaround (Cannot accept a std::vector* with pybind)
                if method == "integrate" and ret == "int":
                    continue
                mapped = math_structure_mutating_methods.get(method, None)
                if mapped is None:
                    continue

                def parse_param(param: str) -> tuple[str, str, str | None]:
                    if "=" in param:
                        decl, default = param.split("=")
                    else:
                        decl, default = param, None
                    type, name = (
                        decl.replace("&", "& ")
                        .replace("*", "* ")
                        .strip()
                        .rsplit(" ", 1)
                    )
                    return (type, name, default)

                parsed_params = [parse_param(param) for param in params.split(",")]

                exposed_params = []
                for type, name, default in parsed_params:
                    cast_default = True
                    for pattern, override in math_structure_overrides.items():
                        if pattern in type:
                            if override[0] is None:
                                name = None
                            else:
                                type = type.replace(pattern, override[0])
                            default = override[1]
                            cast_default = override[2]
                            break

                    if cast_default and default:
                        default = f"static_cast<{type}>({default.strip()})"

                    exposed_params.append((type, name, default))

                params_no_defaults = ", ".join(
                    f"{type} {name}"
                    for type, name, _, in exposed_params
                    if name is not None
                )
                args = ", ".join(
                    f"{name}" if name else default
                    for _, name, default in exposed_params
                )

                with impl.indent(
                    f'.def("{mapped}", [](MathStructure const& self, {params_no_defaults}) -> MathStructureRef {{\n'
                ):
                    impl.write(
                        "MathStructureRef result = MathStructureRef::construct(self);\n"
                    )
                    if ret == "bool":
                        impl.write(f"if(!result->{method}({args})) return nullptr;\n")
                    else:
                        raise RuntimeError(
                            f"Mutating MathStructure method return type {ret} handling not implemented"
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
            f'qalc_class_<{class_}> {name.lower()}(class_, "{snake_to_pascal(name)}", class_, py::is_final{{}});\n'
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

declaration = extract_declaration("struct", "ExpressionName", expression_item_h)
assert declaration is not None
process_options_declaration(
    "ExpressionName",
    declaration,
    {"priv"},
    func_name="add_expression_name_auto",
    define_new_default=True,
    pass_by_type={"std::string": "std::string_view"},
)

properties_for(
    "ExpressionItem",
    expression_item_h,
    {"refcount": None, "type": None, "subtype": None, "id": None, "countNames": None},
    qalc_class=True,
)

BUILTIN_FUNCTION_REGEX = re.compile("^DECLARE_BUILTIN_FUNCTION.*?\\(([a-zA-Z_]+),\\s+([a-zA-Z_]+)\\)", re.MULTILINE)

with function_declaration("void add_builtin_functions(py::module_ &m)"):
    for match in BUILTIN_FUNCTION_REGEX.finditer(builtin_functions_h):
        name, id = match.groups()
        impl.write(f'(void)qalc_class_<{name}, MathFunction>(m, "{name}");\n')

header.close()
impl.close()
