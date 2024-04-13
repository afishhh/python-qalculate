from dataclasses import dataclass
import string
from typing import Iterable, Iterator, Literal

from generate.utils import PeekableIterator, find_any, find_any_not


@dataclass
class Token:
    Type = Literal["comment", "punct", "literal", "ident", "whitespace"]

    type: Type
    text: str


def tokenize(text: str) -> Iterable[Token]:
    identifier_disallowed = string.whitespace + string.punctuation.replace(
        "_", ""
    ).replace("$", "")

    LEN2_PUNCT = {
        "::",
        "+=",
        "-=",
        "*=",
        "/=",
        "|=",
        "&=",
        "->",
        "||",
        "&&",
        "==",
        "!=",
        "<=",
        ">=",
        "++",
        "--",
    }
    LEN3_PUNCT = {"..."}

    while text:
        if text[0] in string.whitespace:
            end = find_any_not(text, string.whitespace)
            yield Token("whitespace", text[:end])
            if end == -1:
                break
            text = text[end:]

        if text.startswith("//"):
            end = text.find("\n")
            yield Token("comment", text[:end])
            text = text[end:]
        elif text.startswith("/*"):
            end = text.find("*/")
            yield Token("comment", text[2 : end - 1])
            text = text[end + 2 :]
        elif text.startswith("#"):
            text = text[text.find("\n") :]
        elif text[0] in string.punctuation:
            if text[0] == '"':
                i = 0
                while (i := i + 1) < len(text):
                    if text[i] == "\\":
                        i += 1
                    elif text[i] == '"':
                        yield Token("literal", text[: i + 1])
                        text = text[i + 1 :]
                        break
                else:
                    raise ValueError("unterminated string literal")
                continue

            if len(text) >= 3 and text[:3] in LEN3_PUNCT:
                token_length = 3
            elif len(text) >= 2 and text[:2] in LEN2_PUNCT:
                token_length = 2
            else:
                token_length = 1

            yield Token("punct", text[:token_length])
            text = text[token_length:]
        else:
            next = find_any(text, identifier_disallowed)
            yield Token("ident", text[:next])
            text = text[next:]


def join_tokens(tokens: Iterable[Token]) -> str:
    result = ""
    for token in tokens:
        if token.type == "whitespace":
            result += " "
        elif token.type in ("ident", "punct"):
            result += token.text
    return result.strip()


def consume_block(
    iterator: Iterator[Token], starter: str = "{", ender: str = "}"
) -> Iterable[Token]:
    level = 1
    for token in iterator:
        if token.text == starter:
            level += 1
        elif token.text == ender:
            level -= 1
            if level == 0:
                break
        else:
            yield token


def skip_noncode(it: PeekableIterator[Token]):
    while (token := it.peek()) is not None and token.type in ("comment", "whitespace"):
        next(it)


def filter_noncode(it: Iterable[Token]) -> Iterable[Token]:
    for token in it:
        if token.type not in ("comment", "whitespace"):
            yield token