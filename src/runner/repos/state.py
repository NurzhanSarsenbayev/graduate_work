from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlState


class StateRepo:
    async def get(self, session: AsyncSession, pipeline_id: str) -> EtlState | None:
        return await session.get(EtlState, pipeline_id)

    async def upsert(
        self, session: AsyncSession, pipeline_id: str, *, last_value: str, last_id: str
    ) -> None:
        state = await session.get(EtlState, pipeline_id)
        if state is None:
            state = EtlState(pipeline_id=pipeline_id)
            session.add(state)
        state.last_processed_value = last_value
        state.last_processed_id = last_id
