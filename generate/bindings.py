from dataclasses import dataclass
from io import StringIO
from typing import Literal, overload

from generate.parsing import (
    Parameter,
    ParsedSource,
    PointerType,
    SimpleType,
    Struct,
    Type,
)
from generate.utils import IndentedWriter, cpp_string


class _LingeringStringIO(StringIO):
    def close(self):
        pass

    def real_close(self):
        super().close()


class _KwOnly:
    pass


KW_ONLY = _KwOnly()


@dataclass
class _Method:
    return_type: Type
    name: str
    receiver: Parameter | None
    body: _LingeringStringIO
    parameters: list[Parameter | _KwOnly]
    extra: list[str]


class PyProperty:
    def __init__(
        self,
        parent: "PyClass",
        name: str,
        static: bool,
        docstring: str,
    ) -> None:
        self._parent = parent
        self._name = name
        self._static = static
        self._docstring = docstring
        self._getter = None
        self._setter = None

    @overload
    def getter(self, expression: str, *, type: Type | str): ...
    @overload
    def getter(self, *, type: Type | str) -> IndentedWriter: ...

    def getter(self, expression: str | None = None, *, type: Type | str):
        if isinstance(type, str):
            type = Type.parse(type)

        if expression is None:
            self._getter = (_LingeringStringIO(), type)
            return IndentedWriter(self._getter[0])
        else:
            self._getter = (expression, type)

    @overload
    def setter(self, expression: str, *, param_type: Type | str): ...
    @overload
    def setter(self, *, param_type: Type | str) -> IndentedWriter: ...

    def setter(self, expression: str | None = None, *, param_type: Type | str = ""):
        if expression is None:
            if isinstance(param_type, str):
                param_type = Type.parse(param_type)
            self._setter = (_LingeringStringIO(), param_type)
            return IndentedWriter(self._setter[0])
        else:
            self._setter = expression


@dataclass
class _Field:
    type: Type
    name: str
    cpp_name: str
    docstring: str
    writeable: bool


class PyClass:
    def __init__(
        self,
        name: str,
        *,
        wrapper: str | None = None,
        bound_type: Struct | str | None = None,
        extra: list[str] = [],
        bases: list[str] = [],
        sources: ParsedSource | None = None,
    ) -> None:
        if bound_type is None:
            bound_type = name

        self._name = name
        if isinstance(bound_type, Struct):
            self._underlying_struct = bound_type
            bound_type = bound_type.name
        else:
            assert sources is not None
            try:
                self._underlying_struct = sources.structure(bound_type)
            except KeyError:
                self._underlying_struct = None
        self._impl_type_name = wrapper or bound_type
        self._bound_type = bound_type
        self._pyclass = f"pybind11::class_<{wrapper or bound_type}"
        for extra_arg in extra:
            self._pyclass += f", {extra_arg}"
        for base in bases:
            self._pyclass += f", {base}"
        self._pyclass += ">"
        self._bases = bases
        self._methods: list[_Method] = []
        self._fields: list[_Field] = []
        self._properties: list[PyProperty] = []

    @property
    def name(self) -> str:
        return self._name

    @property
    def underlying_name(self) -> str:
        return self._bound_type

    @property
    def underlying_type(self) -> Struct:
        assert self._underlying_struct
        return self._underlying_struct

    @property
    def implementation_name(self):
        return self._impl_type_name

    def init(self, *params: str | Parameter | _KwOnly) -> IndentedWriter:
        return self.method(
            "__init_return_type_dont_use", "__init__", *params, receiver=None
        )

    def method(
        self,
        return_type: str | Type,
        name: str,
        *params: str | Parameter | _KwOnly,
        receiver: str | Parameter | Literal["auto"] | None = "auto",
        operator: bool = False,
    ) -> IndentedWriter:
        if isinstance(return_type, str):
            return_type = Type.parse(return_type)
        if receiver == "auto":
            receiver = Parameter(
                type=Type.parse(f"{self._bound_type} const&"), name="self"
            )
        if isinstance(receiver, str):
            receiver = Parameter.parse(receiver)
        if receiver is not None:
            assert receiver.default is None

        writer = _LingeringStringIO()
        extra = []
        if operator:
            extra.append("pybind11::is_operator{}")
        self._methods.append(
            _Method(
                return_type=return_type,
                name=name,
                receiver=receiver,
                body=writer,
                parameters=[
                    Parameter.parse(param) if isinstance(param, str) else param
                    for param in params
                ],
                extra=extra,
            )
        )
        return IndentedWriter(writer)

    def property(
        self, name: str, static: bool = False, docstring: str = ""
    ) -> PyProperty:
        self._properties.append(
            PyProperty(
                self,
                name=name,
                static=static,
                docstring=docstring,
            )
        )
        return self._properties[-1]

    def field(
        self,
        type: Type,
        name: str,
        cpp_name: str,
        *,
        mode: Literal["readonly", "readwrite"] = "readonly",
        docstring: str = "",
    ):
        self._fields.append(
            _Field(type, name, cpp_name, docstring, mode == "readwrite")
        )

    def write_init_calls(self, writer: IndentedWriter):
        for field in self._fields:
            writer.write(".def")
            if field.writeable:
                writer.write("_readwrite")
            else:
                writer.write("_readonly")

            writer.write(
                f"({cpp_string(field.name)}, &{self._bound_type}::{field.cpp_name})\n"
            )

        for property in self._properties:
            writer.write(".def_property")
            if property._static:
                writer.write("_static")
            if property._setter is None:
                writer.write("_readonly")

            assert property._getter is not None
            getter = property._getter[0]

            writer.write(f"({cpp_string(property._name)}, ")
            if isinstance(getter, str):
                writer.write(getter)
            else:
                writer.write("[](")
                if not property._static:
                    writer.write(f"{self._bound_type} const& self")
                with writer.indent(") {"):
                    writer.write(getter.getvalue())
                writer.write("}")

            if setter := property._setter:
                if isinstance(setter, str):
                    writer.write(f", {setter}")
                else:
                    writer.write(f", [](")
                    if not property._static:
                        writer.write(f"{self._bound_type} const& self, ")
                    writer.write(f"{setter[1]} value")
                    with writer.indent(") {"):
                        writer.write(setter[0].getvalue())
                    writer.write("}")

            writer.write(")\n")

        for method in self._methods:
            writer.write(".def")
            if not method.receiver and method.name != "__init__":
                writer.write("_static")

            if method.name == "__init__":
                assert method.receiver is None
                assert method.extra == []
                writer.write(f"(pybind11::init(")
            else:
                writer.write(f"({cpp_string(method.name)}, ")

            writer.write(f"[](")
            first_param = True
            if method.receiver:
                first_param = False
                writer.write(f"{method.receiver.type} {method.receiver.name}")
            for param in method.parameters:
                if not isinstance(param, _KwOnly):
                    if not first_param:
                        writer.write(", ")
                    else:
                        first_param = False
                    writer.write(f"{param.type} {param.name}")
            writer.write(")")

            if method.name != "__init__":
                writer.write(f" -> {method.return_type}")

            with writer.indent("{\n"):
                writer.write(method.body.getvalue())
            writer.write("}")

            if method.name == "__init__":
                writer.write(")")

            for extra in method.extra:
                writer.write(f", {extra}")
            for param in method.parameters:
                if isinstance(param, _KwOnly):
                    writer.write(", pybind11::kw_only{}")
                else:
                    assert param.name
                    writer.write(f", pybind11::arg({cpp_string(param.name)})")
                    if param.default:
                        writer.write(f" = {param.default}")
            writer.write(")\n")

    def write_pyclass_expression(self, writer: IndentedWriter, module_expression: str):
        writer.indent(f"{self._pyclass}({module_expression}, {cpp_string(self.name)})")
        if not self._fields and not self._methods and not self._properties:
            writer.dedent()
            return
        writer.write("\n")
        self.write_init_calls(writer)
        writer.dedent()

    def write_init_function(
        self,
        name: str,
        header: IndentedWriter,
        impl: IndentedWriter,
        *,
        mode: Literal["create", "modify"] = "modify",
    ):
        if mode == "modify":
            header.write(f"{self._pyclass} &{name}({self._pyclass} &class_);\n")
            impl.indent(f"{self._pyclass} &{name}({self._pyclass} &class_) {{\n")
            impl.indent("return class_\n")
            self.write_init_calls(impl)
            impl.dedent(";\n")
        else:
            header.write(f"{self._pyclass} {name}(pybind11::module_ &m);\n")
            impl.indent(f"{self._pyclass} {name}(pybind11::module_ &m) {{\n")
            impl.write(f"return ")
            self.write_pyclass_expression(impl, "m")
            impl.write(";\n")

        impl.dedent("}\n")

    def write_types(self, types: IndentedWriter):
        types.write(f"class {self.name}(")
        for base in self._bases:
            types.write(base)
        types.indent("):\n")

        if not self._fields and not self._methods and not self._properties:
            types.write("pass\n")

        def pythonize_type(type: Type) -> str:
            while isinstance(type, PointerType):
                type = type.inner
            assert isinstance(type, SimpleType)
            # Take types out of pointer wrappers
            if type.targs:
                type = type.targs[0]
                assert isinstance(type, SimpleType)
            if type.name.endswith("int") or type.name in ("size_t"):
                return "int"
            if type.name in ("std::string", "std::string_view"):
                return "str"
            if type.name == "bool":
                return "bool"
            if type.name in ("float", "double"):
                return "float"
            if type.name == "void":
                return "None"
            return repr(type.name)

        prop_like: list[tuple[str, Type, bool, str]] = []

        for field in self._fields:
            prop_like.append((field.name, field.type, True, field.docstring))

        for prop in self._properties:
            assert prop._getter
            prop_like.append((prop._name, prop._getter[1], prop._setter is not None, prop._docstring))

        for name, type, writeable, docstring in prop_like:
            types.write("@property\n")
            return_type = pythonize_type(type)
            with types.indent(f"def {name}(self) -> {return_type}:\n"):
                if docstring:
                    types.write(f'"""{repr(docstring)[1:-1]}"""\n')
                types.write("...\n")

            if writeable:
                types.write(f"@{name}.setter\n")
                with types.indent(f"def {name}(self, value: {return_type}) -> None:\n"):
                    types.write("...\n")

            types.write("\n")

        for method in self._methods:
            types.write(f"def {method.name}(")
            has_self = method.receiver or method.name == "__init__"
            if has_self:
                types.write("self")
            for parameter in method.parameters:
                if has_self or parameter is not method.parameters[0]:
                    types.write(", ")
                if isinstance(parameter, _KwOnly):
                    types.write("*")
                else:
                    types.write(f"{parameter.name}: {pythonize_type(parameter.type)}")
                    if parameter.default:
                        types.write(" = ...")
            types.write(")")
            if method.name != "__init__":
                types.write(f" -> {pythonize_type(method.return_type)}")
            types.write(": ...\n\n")

        types.dedent()
