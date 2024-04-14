from collections import deque
from pathlib import Path
import string
from typing import (
    Callable,
    ContextManager,
    Iterable,
    Iterator,
    Sequence,
    TextIO,
    TypeVar,
)


class _Dedenter:
    def __init__(self, parent: "IndentedWriter") -> None:
        self._parent = parent

    def __enter__(self):
        return None

    def __exit__(self, type, value, traceback):
        return self._parent.dedent()


class IndentedWriter:
    def __init__(self, inner: Path | TextIO, indent: str = "    ") -> None:
        if isinstance(inner, Path):
            self._inner = inner.open("w+")
        else:
            self._inner = inner
        self._indent_level = 0
        self._single_indent = indent
        self._mid_line = False

    @property
    def _indent(self):
        return self._single_indent * self._indent_level

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()

    def close(self):
        self._inner.close()

    def writelines(self, lines: list[str]):
        for line in lines:
            if not self._mid_line:
                self._inner.write(self._indent)
            self._inner.write(line)
            self._mid_line = not line.endswith("\n")

    def write(self, text: str):
        self.writelines(text.splitlines(keepends=True))

    def indent(self, text: str = "") -> ContextManager[None]:
        self.write(text)
        self._indent_level += 1
        return _Dedenter(self)

    def dedent(self, text: str = ""):
        self._indent_level -= 1
        self.write(text)


T = TypeVar("T")


def find_any(text: str, chars: str) -> int:
    for i, c in enumerate(text):
        if c in chars:
            return i
    return -1


def find_any_not(text: str, chars: str) -> int:
    for i, c in enumerate(text):
        if c in chars:
            continue
        else:
            return i
    return -1


def generic_split(things: Iterable[T], sep: T) -> Iterable[list[T]]:
    current = []
    for thing in things:
        if thing == sep:
            if current:
                yield current
                current = []
        else:
            current.append(thing)
    if current:
        yield current


def find(things: Sequence[T], checker: Callable[[T], bool], start: int = 0) -> int:
    if not things:
        return -1
    if start < 0:
        start = len(things) + start

    for i in range(start, len(things)):
        if checker(things[i]):
            return i
    return -1


def split_once(
    things: Sequence[T], checker: Callable[[T], bool], start: int = 0
) -> tuple[Sequence[T], T, Sequence[T]]:
    idx = find(things, checker, start)
    return things[idx:], things[idx], things[idx + 1 :]


def reverse_find(
    things: Sequence[T], checker: Callable[[T], bool], start: int = -1
) -> int:
    if not things:
        return -1
    if start < 0:
        start = len(things) + start

    for i in range(start, -1, -1):
        if checker(things[i]):
            return i
    return -1


def camel_to_snake(name: str):
    while (i := find_any(name, string.ascii_uppercase)) != -1:
        name = name[:i] + "_" + name[i].lower() + name[i + 1 :]
    return name

def camel_to_pascal(name: str):
    return name[0].upper() + name[1:]

def pascal_to_snake(name: str):
    name = name[0].lower() + name[1:]
    return camel_to_snake(name)


def snake_to_pascal(name: str):
    return "".join(part.capitalize() for part in name.split("_"))


def snake_to_camel(name: str):
    name = snake_to_pascal(name)
    name = name[0].lower() + name[1:]
    return name


class PeekableIterator(Iterator[T]):
    def __init__(self, inner: Iterable[T]) -> None:
        self._inner = iter(inner)
        self._queue: deque[T] = deque()

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self._queue:
            value = self._queue.popleft()
            return value
        else:
            return next(self._inner)

    def put_back(self, item: T):
        self._queue.append(item)

    def peek(self) -> T | None:
        if self._queue:
            return self._queue[0]

        try:
            value = next(self._inner)
        except StopIteration:
            return None

        self.put_back(value)

        return value

    def peeker(self) -> "PeekingIterator[T]":
        return PeekingIterator(self)


class PeekingIterator(Iterator[T]):
    def __init__(self, parent: PeekableIterator[T]) -> None:
        self._parent = parent
        self._qidx = 0

    def __iter__(self) -> Iterator[T]:
        return self

    def __next__(self) -> T:
        if self._qidx < len(self._parent._queue):
            value = self._parent._queue[self._qidx]
            self._qidx += 1
            return value
        value = next(self._parent._inner)
        self._parent._queue.append(value)
        self._qidx += 1
        return value

    def commit(self):
        self._parent._queue = deque(list(self._parent._queue)[self._qidx :])
        self._qidx = 0
