"""Artifact storage port (raw provider payloads, exports)."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class ArtifactStorage(Protocol):
    name: str

    def put(self, key: str, data: bytes, content_type: str = "application/octet-stream") -> str:
        """Store bytes and return a storage URI."""
        ...

    def get(self, key: str) -> bytes | None: ...
