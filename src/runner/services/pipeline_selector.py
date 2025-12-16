from __future__ import annotations

from typing import List

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline


async def get_active_pipelines(session: AsyncSession) -> List[EtlPipeline]:
    """Вернуть пайплайны, которые нужно обработать сейчас.

    Правила:
    - enabled = TRUE
    - status IN (RUN_REQUESTED, PAUSE_REQUESTED)
    """
    stmt = (
        select(EtlPipeline)
        .where(EtlPipeline.enabled.is_(True))
        .where(
            or_(
                EtlPipeline.status == PipelineStatus.RUN_REQUESTED.value,
                EtlPipeline.status == PipelineStatus.PAUSE_REQUESTED.value,
            )
        )
        .order_by(EtlPipeline.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
