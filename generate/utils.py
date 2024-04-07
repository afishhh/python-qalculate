from pathlib import Path
from typing import ContextManager, TextIO


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
