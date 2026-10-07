"""Durable mixed-resource inbox contract."""

from typing import Protocol

from personal_os.domain.resources import ResourceCapture, ResourceRecord, ResourceStatus


class ResourceInbox(Protocol):
    async def upsert_many(
        self,
        resources: tuple[ResourceCapture, ...],
        *,
        replace_tags: bool = False,
    ) -> tuple[ResourceRecord, ...]: ...

    async def list_inbox(self, limit: int = 100) -> tuple[ResourceRecord, ...]: ...

    async def list_by_status(
        self,
        status: ResourceStatus,
        limit: int = 100,
    ) -> tuple[ResourceRecord, ...]: ...

    async def set_status(
        self,
        resource_keys: tuple[str, ...],
        status: ResourceStatus,
    ) -> tuple[ResourceRecord, ...]: ...
