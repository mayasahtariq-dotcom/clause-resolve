"""Background job port."""

from __future__ import annotations

from typing import Protocol, runtime_checkable
from uuid import UUID


@runtime_checkable
class JobQueue(Protocol):
    name: str
    durable: bool  # survives process restarts

    def submit_investigation(self, investigation_id: UUID) -> None: ...

    def health_check(self) -> None: ...
