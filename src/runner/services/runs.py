from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus, RunStatus
from src.app.models import EtlPipeline, EtlRun

logger = logging.getLogger("etl_runner")


def utcnow_naive() -> datetime:
    """UTC-время без tzinfo, чтобы ложилось в TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def start_run(session: AsyncSession, pipeline: EtlPipeline) -> EtlRun:
    """Создать запись в etl_runs со статусом RUNNING."""
    run = EtlRun(
        id=str(uuid4()),
        pipeline_id=pipeline.id,
        status=RunStatus.RUNNING.value,
        started_at=utcnow_naive(),
        rows_read=0,
        rows_written=0,
    )
    session.add(run)
    await session.flush()
    logger.info(
        "Started ETL run id=%s for pipeline id=%s name=%s",
        run.id,
        pipeline.id,
        pipeline.name,
    )
    return run


async def finish_run_success(
    session: AsyncSession,
    pipeline: EtlPipeline,
    run: EtlRun,
    rows_read: int,
    rows_written: int,
) -> None:
    """Отметить успешное завершение запуска."""
    run.status = RunStatus.SUCCESS.value
    run.finished_at = utcnow_naive()
    run.rows_read = rows_read
    run.rows_written = rows_written

    pipeline.status = PipelineStatus.IDLE.value

    await session.commit()
    logger.info(
        "Finished ETL run id=%s for pipeline id=%s name=%s: SUCCESS (read=%d, written=%d)",
        run.id,
        pipeline.id,
        pipeline.name,
        rows_read,
        rows_written,
    )


async def finish_run_failed(
    session: AsyncSession,
    pipeline: EtlPipeline,
    run: EtlRun,
    error_message: str,
) -> None:
    """Отметить неуспешное завершение запуска."""
    run.status = RunStatus.FAILED.value
    run.finished_at = utcnow_naive()
    run.error_message = error_message[:1000]

    pipeline.status = PipelineStatus.FAILED.value

    await session.commit()
    logger.error(
        "ETL run id=%s for pipeline id=%s name=%s FAILED: %s",
        run.id,
        pipeline.id,
        pipeline.name,
        error_message,
    )
