from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import get_db_session
from src.app.services.pipelines import PipelinesService


def get_pipelines_service(
    session: AsyncSession = Depends(get_db_session),
) -> PipelinesService:
    """Фабрика PipelinesService для DI.

    Вынесена в отдельный модуль, чтобы в роутере не держать DI-логику.
    """
    return PipelinesService(session=session)
