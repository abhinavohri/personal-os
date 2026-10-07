"""Durable mixed-resource inbox contract."""

from typing import Protocol

from personal_os.domain.resources import ResourceCapture, ResourceRecord


class ResourceInbox(Protocol):
    async def upsert_many(
        self, resources: tuple[ResourceCapture, ...]
    ) -> tuple[ResourceRecord, ...]: ...

    async def list_inbox(self, limit: int = 50) -> tuple[ResourceRecord, ...]: ...

