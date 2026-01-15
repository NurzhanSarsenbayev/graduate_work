from __future__ import annotations

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from infra.db import get_db_session
from src.app.services.pipelines import PipelinesService


def get_pipelines_service(
    session: AsyncSession = Depends(get_db_session),
) -> PipelinesService:
    """Factory for creating PipelinesService instances
     for dependency injection.

    This is extracted into a separate module to keep routers
    free of DI-related logic.
    """
    return PipelinesService(session=session)
