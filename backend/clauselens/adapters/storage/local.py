"""Artifact storage adapters: local filesystem and a no-op."""

from __future__ import annotations

import re
from pathlib import Path

from clauselens.config import Settings

_SAFE_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/-]{0,250}$")


class LocalFileStorage:
    name = "local"

    def __init__(self, root: str) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if not _SAFE_KEY.match(key) or ".." in key:
            raise ValueError(f"unsafe storage key: {key!r}")
        path = (self._root / key).resolve()
        if self._root not in path.parents:
            raise ValueError("storage key escapes root")
        return path

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return f"file://{path}"

    def get(self, key: str) -> bytes | None:
        path = self._path(key)
        return path.read_bytes() if path.exists() else None


class NullStorage:
    name = "none"

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        return ""

    def get(self, key: str) -> bytes | None:
        return None


def create_local(settings: Settings) -> LocalFileStorage:
    return LocalFileStorage(settings.storage_local_path)


def create_null(settings: Settings) -> NullStorage:
    return NullStorage()
