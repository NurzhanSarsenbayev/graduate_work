from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlPipeline, EtlRun


class PipelinesRepository(Protocol):
    async def list_pipelines(self, session: AsyncSession) -> Sequence[EtlPipeline]: ...

    async def get_pipeline(self, session: AsyncSession, pipeline_id: str) -> EtlPipeline: ...

    async def create_pipeline(self, session: AsyncSession, payload) -> EtlPipeline: ...

    async def update_pipeline_status(
        self, session: AsyncSession, pipeline_id: str, new_status: str
    ) -> EtlPipeline: ...

    async def update_pipeline(
        self, session: AsyncSession, pipeline_id: str, data: dict
    ) -> EtlPipeline: ...

    async def list_pipeline_runs(
        self, session: AsyncSession, pipeline_id: str, limit: int
    ) -> Sequence[EtlRun]: ...
