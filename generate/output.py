from io import StringIO
from pathlib import Path
import json
import hashlib
from typing import TextIO

class _OutputWriter(StringIO):
    def __init__(self, parent: "OutputDirectory", path: Path):
        super().__init__()
        self._parent = parent
        self._path = path

    def close(self) -> None:
        self._parent.write(self._path, self.getvalue())
        return super().close()

class OutputDirectory:
    @property
    def _index_path(self) -> Path:
        return self._path / "output_index.json"

    def _hash(self, text: str) -> str:
        return hashlib.sha1(text.encode(), usedforsecurity=False).digest().hex()

    def __init__(self, path: Path) -> None:
        self._path = path
        self._path.mkdir(exist_ok=True)
        try:
            self._index: dict[str, str] = json.loads(self._index_path.read_text())
        except FileNotFoundError:
            self._index: dict[str, str] = {}

    @property
    def path(self) -> Path:
        return self._path

    def write(self, path: Path, content: str):
        if not path.is_absolute():
            path = self._path / path
        assert path.is_relative_to(self._path)

        index_key = str(path)
        new_hash = self._hash(content)
        if self._index.get(index_key, None) != new_hash:
            self._index[index_key] = new_hash
            path.write_text(content)
        else:
            print(f"skipped writing unchanged path {path.relative_to(self._path)}")

    def writer(self, path: Path | str) -> TextIO:
        return _OutputWriter(self, Path(path))

    def close(self):
        self._index_path.write_text(json.dumps(self._index))
