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
    name: str, text: str, renames: dict[str, str | None] = {}
):
    PROPERTY_REGEX = re.compile("([a-zA-Z_]+)\\s+([a-zA-Z_]+)\\(\\) const;")

    class_type = (
        f"pybind11::class_<{name}>" if name != "MathStructure" else MATH_STRUCTURE_CLASS
    )

    with function_declaration(
        f"{class_type} &add_{pascal_to_snake(name)}_properties({class_type} &class_)"
    ):
        with impl.indent("return class_\n"):
            for line in text.splitlines()[1:-1]:
                if match := PROPERTY_REGEX.match(line.strip()):
                    _, prop = match.groups()
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
    name: str, text: str, exclude: set[str], override_class=None
):
    declarations = text.splitlines()[1:-1]
    field_regex = re.compile("([a-zA-Z_]+)\\s+([a-zA-Z_]+);")

    with function_declaration(
        f"void add_{pascal_to_snake(name)}(pybind11::module_ &m)"
    ):
        with impl.indent(f'pybind11::class_<{override_class or name}>(m, "{name}")\n'):
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
                impl.write(f"{type} {field}")
            with impl.indent(") {\n"):
                impl.write(f"{name} result;\n")
                for field, type in options:
                    impl.write(f"result.{field} = {field};\n")
                impl.write(f"return result;\n")
            impl.write("}), py::kw_only{}")
            for field, type in options:
                impl.write(
                    f', py::arg("{field}") = default_{pascal_to_snake(name)}.{field}'
                )
            impl.write(")\n")

            with impl.indent(f'.def("__repr__", [](py::object s) {{\n'):
                impl.write(f'std::string output = "{name}(";\n')
                impl.write(f"output.reserve(512);\n")
                for i, (field, type) in enumerate(options):
                    if i != 0:
                        impl.write(f'output += ", ";\n')
                    impl.write(f'output += "{field}=";\n')
                    impl.write(
                        f'output += s.attr("{field}").attr("__repr__")().cast<std::string>();\n'
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


def properties_for(name: str, text: str, renames: dict[str, str | None] = {}):
    declaration = extract_declaration("class", name, text)
    assert declaration is not None
    process_simple_properties(name, declaration, renames)


properties_for(
    "Number",
    number_h,
    {"floatValue": None, "integer": None, "getBoolean": None},
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
        "countChildren": None,
        "refcount": None,
        "isAborted": None,
        "rows": None,
        "size": None,
        "type": None,
        "comparisonType": None,
        # Remove type-specific checks (use instanceof instead)
        **{f"is{snake_to_pascal(name)}": None for name in structure_types},
        **{f: None for f in ("isDateTime", "isMatrix")},
    },
)

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
            f'qalc_class_<{class_}> {name.lower()}(class_, "{snake_to_pascal(name)}", class_);\n'
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

header.close()
impl.close()