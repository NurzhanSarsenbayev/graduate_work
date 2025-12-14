from __future__ import annotations

from typing import List

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline


async def get_active_pipelines(session: AsyncSession) -> List[EtlPipeline]:
    """Вернуть пайплайны, которые нужно исполнять сейчас.

    Правила:
    - enabled = TRUE
    - status = RUNNING
    """
    stmt = (
        select(EtlPipeline)
        .where(EtlPipeline.enabled.is_(True))
        .where(EtlPipeline.status == PipelineStatus.RUNNING.value)
        .order_by(EtlPipeline.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())
