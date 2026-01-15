from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException, status

from src.app.core.exceptions import PipelineNotFoundError
from src.app.schemas.pipelines import PipelineOut
from src.app.services.pipelines import PipelinesService


async def get_pipeline_or_404(
    service: PipelinesService,
    pipeline_id: UUID,
) -> PipelineOut:
    """Get a pipeline or raise HTTP 404."""
    try:
        pipeline = await service.get_pipeline(str(pipeline_id))
    except PipelineNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    return PipelineOut.model_validate(pipeline)


def http_400(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=detail,
    )


def http_404(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=detail,
    )


def http_409(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=detail,
    )
