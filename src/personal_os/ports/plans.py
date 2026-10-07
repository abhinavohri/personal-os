"""Durable plan-proposal contract used by the approval workflow."""

from datetime import datetime
from typing import Protocol

from personal_os.domain.plans import PlanProposal


class PlanProposalStore(Protocol):
    async def upsert_draft(self, proposal: PlanProposal) -> PlanProposal: ...

    async def get(self, proposal_key: str) -> PlanProposal | None: ...

    async def latest_draft(self) -> PlanProposal | None: ...

    async def mark_published(
        self,
        proposal_key: str,
        task_ids: tuple[str, ...],
        published_at: datetime,
    ) -> PlanProposal: ...

