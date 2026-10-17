import asyncio
import contextlib
import os
import re
from collections.abc import Collection
from pathlib import Path
from uuid import uuid4

_SAFE_KEY = re.compile(r"^[a-z0-9][a-z0-9_.-]*(?:/[a-z0-9][a-z0-9_.-]*)*$")


class LocalObjectStorage:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    @property
    def root(self) -> Path:
        return self._root

    async def put(self, key: str, data: bytes, *, content_type: str) -> None:
        await asyncio.to_thread(self._write, self._path(key), data)

    async def delete(self, keys: Collection[str]) -> None:
        paths = [self._path(key) for key in keys]
        await asyncio.to_thread(self._remove, paths)

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.fullmatch(key) or ".." in key:
            raise ValueError(f"Unsafe storage key: {key!r}")
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError(f"Unsafe storage key: {key!r}")
        return path

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        temporary.write_bytes(data)
        os.replace(temporary, path)

    def _remove(self, paths: list[Path]) -> None:
        parents = set()
        for path in paths:
            path.unlink(missing_ok=True)
            parents.add(path.parent)
        for parent in parents:
            with contextlib.suppress(OSError):
                if parent != self._root:
                    parent.rmdir()
