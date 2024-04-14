from abc import ABC, abstractmethod
import enum
from pathlib import Path
import re
import string
from typing import Iterable, Literal, Sequence
from dataclasses import dataclass, field

from .token import (
    Token,
    consume_block,
    filter_noncode,
    join_tokens,
    skip_noncode,
    take_meaningful,
    tokenize,
)
from .utils import PeekableIterator, find, reverse_find, split_once


def find_end_of_block(text: str, start: int = 0) -> int:
    while text[start] in string.whitespace:
        start += 1

    assert text[start] == "{"
    level = 0
    for i, c in enumerate(text[start + 0 :]):
        if c == "}":
            level -= 1
            if level == 0:
                return i + start
        elif c == "{":
            level += 1

    return -1


def take_namespaced_name(it: PeekableIterator[Token]) -> str:
    if (token := it.peek()) is None or token.type != "ident":
        return ""

    result = next(it).text

    while (token := it.peek()) is not None:
        if token.type == "whitespace":
            next(it)
            continue
        elif token.text == "::":
            next(it)
            result += "::"
            result += take_meaningful(it).text
        else:
            break

    return result


@dataclass(frozen=True, slots=True, kw_only=True)
class Type(ABC):
    const: bool = False
    volatile: bool = False


@dataclass(frozen=True, slots=True)
class SimpleType(Type):
    name: str
    targs: list[Type] | None = field(default=None)

    def __str__(self) -> str:
        result = self.name
        if self.targs:
            result += "<"
            result += ", ".join(str(targ) for targ in self.targs)
            result += ">"

        if self.const:
            result += " const"
        if self.volatile:
            result += " volatile"

        return result


@dataclass(frozen=True, slots=True)
class PointerType(Type):
    inner: Type
    kind: Literal["*", "&", "&&"]

    def __str__(self) -> str:
        result = str(self.inner)

        result += self.kind

        if self.const:
            result += " const"
        if self.volatile:
            result += " volatile"

        return result


@dataclass(frozen=True, slots=True)
class ArrayType(Type):
    inner: Type
    size: int | None

    def __str__(self) -> str:
        return f"{self.inner}[{self.size}]"


def take_type_list(tokens: Iterable[Token]) -> list[Type]:
    result = []
    while True:
        it, tokens = take_type(tokens)
        result.append(it)

        if not tokens:
            break

        try:
            it = iter(tokens)
            assert take_meaningful(it).text == ","
            tokens = list(it)
        except StopIteration:
            break
    return result


def take_cv(it: PeekableIterator[Token]) -> tuple[bool, bool]:
    const = False
    volatile = False
    peeker = it.peeker()
    try:
        while (token := take_meaningful(peeker).text) in (
            "const",
            "volatile",
        ):
            if token == "const":
                const = True
            elif token == "volatile":
                volatile = True
            peeker.commit()
    except StopIteration:
        pass

    return (const, volatile)


def take_simple_type(it: PeekableIterator[Token]) -> Type:
    const = False
    volatile = False
    result = ""
    targs: list[Type] | None = None

    while (token := take_meaningful(it)).text in (
        "class",
        "struct",
        "enum",
        "const",
        "volatile",
        "unsigned",
        "signed",
    ):
        if token.text in "unsigned":
            result += token.text
            result += " "
        if token.text == "const":
            const = True
        if token.text == "volatile":
            volatile = True
    it.put_back(token)

    def match_idents(*args: str) -> bool:
        peeker = it.peeker()
        try:
            for arg in args:
                if take_meaningful(peeker).text != arg:
                    return False
            peeker.commit()
            return True
        except StopIteration:
            return False

    if match_idents("long", "double"):
        result += "long double"
    elif match_idents("long", "long", "int") or match_idents("long", "long"):
        result += "long long"
    elif match_idents("long", "int") or match_idents("long"):
        result += "long"
    else:
        result += take_namespaced_name(it)

    result = result.strip()

    if (token := it.peek()) == Token("punct", "<"):
        next(it)
        block = list(consume_block(it, "<", ">"))
        targs = take_type_list(block)

    peeker = it.peeker()
    try:
        while (token := take_meaningful(peeker).text) in (
            "const",
            "volatile",
            "signed",
            "unsigned",
        ):
            if token == "unsigned":
                result = f"{token} {result}"
            elif token == "const":
                const = True
            elif token == "volatile":
                volatile = True
            peeker.commit()
    except StopIteration:
        pass

    return SimpleType(const=const, volatile=volatile, name=result, targs=targs)


# TODO: Handle function pointers
#       This may just as well never be implemented.
def take_type(tokens: Iterable[Token]) -> tuple[Type, Sequence[Token]]:
    it = PeekableIterator(tokens)
    result = take_simple_type(it)

    while True:
        peeker = it.peeker()
        try:
            token = take_meaningful(peeker)
        except StopIteration:
            break

        if token.text in ("*", "&", "&&"):
            peeker.commit()

            const, volatile = take_cv(it)
            kind = token.text

            result = PointerType(
                const=const, volatile=volatile, inner=result, kind=kind
            )
        else:
            break

    return (result, list(it))


@dataclass(frozen=True, slots=True)
class Declaration(ABC):
    name: str


class Accessibility(enum.Enum):
    PRIVATE = "private"
    PROTECTED = "protected"
    PUBLIC = "public"

    @staticmethod
    def parse(string: str) -> "Accessibility":
        try:
            return {
                "public": Accessibility.PUBLIC,
                "protected": Accessibility.PROTECTED,
                "private": Accessibility.PRIVATE,
            }[string]
        except KeyError:
            raise ValueError(f"{string} is not a valid accessibility level")


@dataclass(frozen=True, slots=True)
class Parameter:
    type: Type
    name: str | None
    default: str | None


@dataclass(frozen=True, slots=True)
class Struct(Declaration):
    @dataclass(frozen=True, slots=True)
    class Field:
        accessibility: Accessibility
        docstring: str
        type: Type
        name: str

    @dataclass(frozen=True, slots=True)
    class Method:
        accessibility: Accessibility
        docstring: str
        return_type: Type
        name: str
        params: list[Parameter | Literal["..."]]
        const: bool
        virtual: bool

        @property
        def is_operator(self) -> bool:
            return (
                self.name.startswith("operator") and self.name[8] in string.punctuation
            )

        @property
        def is_constructor(self) -> bool:
            return self.name == "<constructor>"

        @property
        def is_destructor(self) -> bool:
            return self.name == "<destructor>"

    @dataclass(frozen=True, slots=True)
    class Base:
        accessibility: Accessibility
        virtual: bool
        name: str

    bases: list[Base]
    fields: dict[str, Field]
    methods: dict[str, Method]
    # Preserves declaration order
    members: list[Field | Method]


@dataclass(frozen=True, slots=True)
class EnumVariant:
    docstring: str
    name: str


@dataclass(frozen=True, slots=True)
class Enum(Declaration):
    variants: dict[str, EnumVariant]
    # Preserves declaration order
    members: list[EnumVariant]


def _parse_function_params(tokens: Sequence[Token]) -> list[Parameter | Literal["..."]]:
    # C-style no-argument function declaration
    if tokens == [Token(type="ident", text="void")]:
        return []

    result = []

    while tokens:
        if tokens[0].text == "...":
            result.append("...")
            if len(tokens) > 1:
                assert tokens[1].text == ","
                tokens = tokens[2:]
            else:
                tokens = tokens[1:]
            continue

        param_type, tokens = take_type(tokens)

        it = PeekableIterator(tokens)
        if (token := it.peek()) and token.text == "(":
            return []

        if (token := it.peek()) and token.type == "ident":
            param_name = token.text
            next(it)
        else:
            param_name = None

        if (token := it.peek()) and token.text == "[":
            next(it)
            param_type = ArrayType(param_type, size=int(next(it).parse_int()))
            assert next(it).text == "]"

        if (token := it.peek()) and token.text == "=":
            next(it)

            default_tokens = []

            for token in it:
                if token.text == ",":
                    it.put_back(token)
                    break
                else:
                    default_tokens.append(token)

            param_default = join_tokens(default_tokens)
        else:
            param_default = None

        try:
            assert next(it).text == ","
        except StopIteration:
            pass

        tokens = list(it)

        result.append(Parameter(param_type, param_name, param_default))

    return result


def _parse_struct_block(
    name: str,
    tokens: list[Token],
    initial_accessibility: Accessibility,
    bases: list[Struct.Base],
):
    result = Struct(name=name, bases=bases, fields={}, methods={}, members=[])

    it = iter(tokens)
    access = initial_accessibility
    current_comment = ""
    for token in it:
        if token.type == "comment":
            if (comment_text := token.text.removeprefix("///")) is not token.text:
                current_comment += comment_text.strip() + "\n"
            elif (comment_text := token.text.removeprefix("/**")) is not token.text:
                comment_text = comment_text.removesuffix("*/")
                current_comment += comment_text.strip() + "\n"
        elif token.type == "whitespace":
            pass
        else:
            try:
                access = Accessibility.parse(token.text)
                assert next(it).text == ":"
                continue
            except ValueError:
                pass

            line = [token]
            while (token := next(it)).text not in (";", "{"):
                line.append(token)

            if token.text == "{":
                for _ in consume_block(it):
                    pass

            lit = iter(line)
            is_virtual = take_meaningful(lit).text == "virtual"
            if is_virtual:
                rest = list(lit)
            else:
                rest = line

            member_name = None
            lit = PeekableIterator(rest)
            if (token := take_meaningful(lit).text) in ("~", name):
                # Destructor
                if token == "~":
                    member_name = "<destructor>"
                    rest = list(lit)
                else:
                    skip_noncode(lit)
                    # Constructor
                    if lit.peek() == Token("punct", "("):
                        member_name = "<constructor>"
                        rest = list(lit)

            if member_name:
                member_type = SimpleType("void")
                trest = None
            else:
                member_type, trest = take_type(rest)
                _, member_name, rest = split_once(trest, lambda t: t.type == "ident")
                member_name = member_name.text

            if (args_start := find(rest, lambda t: t.text == "(")) != -1:
                last_paren = reverse_find(rest, lambda t: t.text == ")")
                last_colon = reverse_find(rest, lambda t: t.text == ":")
                if last_colon < last_paren:
                    args_end = reverse_find(rest, lambda t: t.text == ")", last_colon)
                else:
                    args_end = last_paren

                # This fixes operator names (otherwise the operator punctuation would be skipped)
                if trest:
                    member_name = join_tokens(
                        trest[: find(trest, lambda t: t.text == "(")]
                    ).replace(" ", "")

                # FIXME: *This is a field* whose type is a function pointer...
                if member_name == "":
                    continue

                const_idx = find(
                    rest,
                    lambda t: t.text == "const",
                    args_end,
                )

                rest = list(filter_noncode(rest[args_start + 1 : args_end]))
                method = Struct.Method(
                    accessibility=access,
                    docstring=current_comment.strip(),
                    return_type=member_type,
                    name=member_name,
                    params=_parse_function_params(rest),
                    const=const_idx != -1,
                    virtual=is_virtual,
                )
                current_comment = ""

                result.methods[method.name] = method
                result.members.append(method)
            else:
                field = Struct.Field(
                    docstring=current_comment.strip(),
                    accessibility=access,
                    type=member_type,
                    name=member_name,
                )
                current_comment = ""
                result.fields[field.name] = field
                result.members.append(field)

    return result


def _parse_enum_block(name: str, tokens: list[Token]) -> Enum:
    result = Enum(name=name, variants={}, members=[])

    it = PeekableIterator(tokens)
    current_comment = ""
    for token in it:
        if token.type == "comment":
            if (comment_text := token.text.removeprefix("///")) is not token.text:
                current_comment += comment_text.strip() + "\n"
            elif (comment_text := token.text.removeprefix("/**")) is not token.text:
                comment_text = comment_text.removesuffix("*/")
                current_comment += comment_text.strip() + "\n"
        elif token.type == "whitespace":
            pass
        else:
            variant = EnumVariant(docstring=current_comment.strip(), name=token.text)
            current_comment = ""

            result.variants[variant.name] = variant
            result.members.append(variant)

            try:
                skip_noncode(it)
                token = next(it)
                if token == Token("punct", "="):
                    while (token := next(it)) != Token("punct", ","):
                        pass
                else:
                    assert token == Token("punct", ",")
            except StopIteration:
                pass

    return result


class ParsedSource(ABC):
    @abstractmethod
    def declaration(self, name: str) -> Declaration:
        pass

    def enum(self, name: str) -> Enum:
        decl = self.declaration(name)
        if not isinstance(decl, Enum):
            raise KeyError(f"{name} is not an enum")
        return decl

    def structure(self, name: str) -> Struct:
        decl = self.declaration(name)
        if not isinstance(decl, Struct):
            raise KeyError(f"{name} is not a structure")
        return decl


def _strip_macro_declarations(text: str) -> str:
    it = text.splitlines()
    result = []
    macro_continued = False
    for line in it:
        if macro_continued:
            macro_continued = line.rstrip().endswith("\\")
            continue
        tmp = line.lstrip()
        if tmp.startswith("#"):
            if tmp.removeprefix("#").lstrip().removeprefix("define"):
                if tmp.rstrip().endswith("\\"):
                    macro_continued = True
                continue
        result.append(line)
    return "\n".join(result)


class ParsedSourceFile(ParsedSource):
    def _extract_declarations(
        self, text: str
    ) -> Iterable[tuple[str, str, list[Token], list[Struct.Base]]]:
        pattern = re.compile(
            r"(struct|enum|class)\s+([a-zA-Z_0-9]+)\s*(?::\s*((?:(public|protected|private|virtual)\s+)*([a-zA-Z_0-9]+)(?:\s*,\s*(?:(public|protected|private|virtual)\s+)*([a-zA-Z_0-9]+))*))?\s*{",
            re.MULTILINE,
        )
        for match in pattern.finditer(text):
            keyword, name, bases, *_ = match.groups()
            block = list(consume_block(tokenize(text[match.end() :])))

            parsed_bases = []
            for base in (bases or "").split(","):
                access = Accessibility.PRIVATE
                virtual = False
                for token in base.split():
                    try:
                        access = Accessibility.parse(token)
                    except ValueError:
                        if token == "virtual":
                            virtual = True
                        else:
                            parsed_bases.append(Struct.Base(access, virtual, token))
                            break
                else:
                    break

            yield (
                keyword,
                name,
                block,
                parsed_bases,
            )

        # TODO: Bring this up to the above cases standards
        pattern = re.compile("typedef\\s+(struct|enum|class)\\s+", re.MULTILINE)
        for match in pattern.finditer(text):
            (keyword,) = match.groups()
            end = find_end_of_block(text, match.end())
            assert end != -1
            name = text[end:].split(maxsplit=2)[1].removesuffix(";")
            yield (
                keyword,
                name,
                list(
                    tokenize(
                        text[match.end() : end + 1]
                        .strip()
                        .removeprefix("{")
                        .removesuffix("}")
                    )
                ),
                [],
            )

    def __init__(self, text: Path | str, filename: str | None = None) -> None:
        if isinstance(text, Path):
            filename = text.name
            text = text.read_text()

        self._filename = filename
        self._text = text
        self._declarations: dict[str, Declaration] = {}

        for kw, name, block, bases in self._extract_declarations(
            _strip_macro_declarations(text)
        ):
            if kw in ("struct", "class"):
                self._declarations[name] = _parse_struct_block(
                    name,
                    block,
                    Accessibility.PRIVATE if kw == "class" else Accessibility.PUBLIC,
                    bases,
                )
            elif kw == "enum":
                self._declarations[name] = _parse_enum_block(name, block)
            else:
                assert False

    def declaration(self, name: str) -> Declaration:
        return self._declarations[name]

    @property
    def filename(self) -> str | None:
        return self._filename

    @property
    def text(self) -> str:
        return self._text


class ParsedSourceFiles(ParsedSource):
    def __init__(self, files: Iterable[Path | ParsedSourceFile]) -> None:
        self._files: list[ParsedSourceFile] = []
        for file in files:
            if isinstance(file, ParsedSourceFile):
                self.add(file)
            else:
                self.add(ParsedSourceFile(file))

    def add(self, path_or_file: Path | ParsedSourceFile):
        if isinstance(path_or_file, Path):
            return self.add(ParsedSourceFile(path_or_file.read_text()))
        self._files.append(path_or_file)

    def declaration(self, name: str) -> Declaration:
        for file in self._files:
            try:
                return file.declaration(name)
            except KeyError:
                pass
        raise KeyError(f"declaration {name} does not exist")

    def get(self, filename: str) -> ParsedSourceFile:
        for file in self._files:
            if file.filename == filename:
                return file
        raise KeyError(f"filename {filename} is not in sources")
