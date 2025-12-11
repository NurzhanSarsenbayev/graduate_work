from __future__ import annotations

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import get_db_session
from src.app.models import EtlPipeline
from src.app.repositories.pipelines import (
    list_pipelines,
    get_pipeline,
    create_pipeline,
    update_pipeline_status,
    update_pipeline,
    list_pipeline_runs
)

router = APIRouter(prefix="/api/v1/pipelines", tags=["pipelines"])

class PipelineCreate(BaseModel):
    name: str
    type: str = "SQL"               # пока только SQL
    mode: str = "full"              # full / incremental
    enabled: bool = True
    target_table: str
    batch_size: int = 1000
    source_query: str
    description: str | None = None

class PipelineOut(BaseModel):
    """Упрощённое представление пайплайна в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    description: str | None = None
    type: str
    mode: str
    enabled: bool
    status: str
    target_table: str
    batch_size: int

class PipelineUpdate(BaseModel):
    """Модель для частичного обновления пайплайна."""

    name: str | None = None
    description: str | None = None
    type: str | None = None           # "SQL" / "PYTHON"
    mode: str | None = None           # "full" / "incremental"
    enabled: bool | None = None
    target_table: str | None = None
    batch_size: int | None = None
    source_query: str | None = None

class PipelineRunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    rows_read: int
    rows_written: int
    error_message: str | None = None

@router.get("/{pipeline_id}", response_model=PipelineOut)
async def get_pipeline_endpoint(
    pipeline_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PipelineOut:
    pipeline: EtlPipeline | None = await get_pipeline(session, str(pipeline_id))
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )
    return PipelineOut.model_validate(pipeline)

@router.post("/", response_model=PipelineOut, status_code=201)
async def create_pipeline_endpoint(
    payload: PipelineCreate,
    session: AsyncSession = Depends(get_db_session),
) -> PipelineOut:
    try:
        pipeline = await create_pipeline(session, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return PipelineOut.model_validate(pipeline)


@router.get("/", response_model=List[PipelineOut])
async def list_pipelines_endpoint(
    session: AsyncSession = Depends(get_db_session),
) -> List[PipelineOut]:
    pipelines = await list_pipelines(session)
    # thanks to model_config.from_attributes, можно просто скормить ORM-модели
    return [PipelineOut.model_validate(p) for p in pipelines]

@router.post("/{pipeline_id}/run", response_model=PipelineOut)
async def run_pipeline_endpoint(
    pipeline_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PipelineOut:
    """Запрос на запуск пайплайна: статус -> RUNNING."""

    pipeline = await update_pipeline_status(session, str(pipeline_id), "RUNNING")
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    return PipelineOut.model_validate(pipeline)

@router.post("/{pipeline_id}/pause", response_model=PipelineOut)
async def pause_pipeline_endpoint(
    pipeline_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> PipelineOut:
    """Запрос на паузу пайплайна: статус -> PAUSED."""

    pipeline = await update_pipeline_status(session, str(pipeline_id), "PAUSED")
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    return PipelineOut.model_validate(pipeline)

@router.patch("/{pipeline_id}", response_model=PipelineOut)
async def update_pipeline_endpoint(
    pipeline_id: UUID,
    payload: PipelineUpdate,
    session: AsyncSession = Depends(get_db_session),
) -> PipelineOut:
    """Частичное обновление пайплайна.

    Простое правило:
    - если пайплайн в статусе RUNNING — запрещаем изменения (кроме как через pause/run).
    """

    pipeline = await get_pipeline(session, str(pipeline_id))
    if pipeline is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Pipeline not found",
        )

    if pipeline.status == "RUNNING":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Cannot update pipeline while it is RUNNING",
        )

    # Берём только те поля, которые реально пришли в запросе
    update_data = payload.model_dump(exclude_unset=True)
    if not update_data:
        # Нечего менять — вернём текущие данные
        return PipelineOut.model_validate(pipeline)

    updated = await update_pipeline(session, str(pipeline_id), update_data)
    return PipelineOut.model_validate(updated)

@router.get(
    "/{pipeline_id}/runs",
    response_model=list[PipelineRunOut],
    summary="Получить историю запусков пайплайна",
)
async def get_pipeline_runs_endpoint(
    pipeline_id: UUID,
    limit: int = Query(50, ge=1, le=500),
    session: AsyncSession = Depends(get_db_session),
) -> list[PipelineRunOut]:
    """Вернуть историю запусков для конкретного пайплайна.

    - 404, если пайплайна не существует;
    - по умолчанию отдаём до 50 последних запусков.
    """
    pipeline = await get_pipeline(session, str(pipeline_id))
    if pipeline is None:
        raise HTTPException(status_code=404, detail="Pipeline not found")

    runs = await list_pipeline_runs(
        session=session,
        pipeline_id=str(pipeline_id),
        limit=limit,
    )
    # благодаря from_attributes можно скармливать ORM-модели
    return [PipelineRunOut.model_validate(r) for r in runs]