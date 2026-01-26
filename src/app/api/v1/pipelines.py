from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status

from src.app.api.helpers.pipelines import (
    get_pipeline_or_404,
    http_400,
    http_404,
    http_409,
)
from src.app.core.exceptions import (
    PipelineIsRunningError,
    PipelineNameAlreadyExistsError,
    PipelineNotFoundError,
)
from src.app.dependencies import get_pipelines_service
from src.app.schemas.pipelines import (
    PipelineCreate,
    PipelineOut,
    PipelineRunOut,
    PipelineUpdate,
)
from src.app.services.pipelines import PipelinesService

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])


@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline_endpoint(
    pipeline_id: UUID,
    service: PipelinesService = Depends(get_pipelines_service),
) -> PipelineOut:
    return await get_pipeline_or_404(service, pipeline_id)


@router.post("/", response_model=PipelineOut, status_code=status.HTTP_201_CREATED)
async def create_pipeline_endpoint(
    payload: PipelineCreate,
    service: PipelinesService = Depends(get_pipelines_service),
) -> PipelineOut:
    try:
        pipeline = await service.create_pipeline(payload)
    except PipelineNameAlreadyExistsError as exc:
        raise http_400(str(exc)) from exc
    except ValueError as exc:
        # target_table is not in ALLOWED_TARGET_TABLES, etc.
        raise http_400(str(exc)) from exc

    return PipelineOut.model_validate(pipeline)


@router.get("/", response_model=list[PipelineOut])
async def list_pipelines_endpoint(
    service: PipelinesService = Depends(get_pipelines_service),
) -> list[PipelineOut]:
    pipelines = await service.list_pipelines()
    return [PipelineOut.model_validate(p) for p in pipelines]


@router.post("/{pipeline_id}/run", response_model=PipelineOut)
async def run_pipeline_endpoint(
    pipeline_id: UUID,
    service: PipelinesService = Depends(get_pipelines_service),
) -> PipelineOut:
    """Pipeline run request: status -> RUN_REQUESTED."""
    try:
        pipeline = await service.run_pipeline(str(pipeline_id))
    except PipelineNotFoundError as exc:
        raise http_404("Pipeline not found") from exc

    return PipelineOut.model_validate(pipeline)


@router.post("/{pipeline_id}/pause", response_model=PipelineOut)
async def pause_pipeline_endpoint(
    pipeline_id: UUID,
    service: PipelinesService = Depends(get_pipelines_service),
) -> PipelineOut:
    """Pipeline pause request: status -> PAUSE_REQUESTED."""
    try:
        pipeline = await service.pause_pipeline(str(pipeline_id))
    except PipelineNotFoundError as exc:
        raise http_404("Pipeline not found") from exc

    return PipelineOut.model_validate(pipeline)


@router.patch("/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline_endpoint(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    service: PipelinesService = Depends(get_pipelines_service),
) -> PipelineOut:
    """Partial pipeline update.

    Rule:
    - if pipeline is RUNNING - prohibit update.
    """
    update_data = payload.model_dump(exclude_unset=True)

    if not update_data:
        return await get_pipeline_or_404(service, pipeline_id)

    try:
        updated = await service.update_pipeline(
            pipeline_id=str(pipeline_id),
            update_data=update_data,
        )
    except PipelineIsRunningError as exc:
        raise http_409(str(exc)) from exc
    except PipelineNotFoundError as exc:
        raise http_404("Pipeline not found") from exc

    return PipelineOut.model_validate(updated)


@router.get(
    "/{pipeline_id}/runs",
    response_model=list[PipelineRunOut],
    summary="Get list of pipeline runs",
)
async def get_pipeline_runs_endpoint(
    pipeline_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    service: PipelinesService = Depends(get_pipelines_service),
) -> list[PipelineRunOut]:
    """Get list of runs for a pipeline."""
    try:
        await service.get_pipeline(str(pipeline_id))
    except PipelineNotFoundError as exc:
        raise http_404("Pipeline not found") from exc

    runs = await service.list_pipeline_runs(
        pipeline_id=str(pipeline_id),
        limit=limit,
    )
    return [PipelineRunOut.model_validate(r) for r in runs]
