from __future__ import annotations

import asyncio
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline
from src.runner.services.db_errors import is_db_disconnect
from src.runner.services.pipeline_control import apply_pause_requested, claim_run_requested, set_status
from src.runner.services.pipeline_snapshot import snapshot_pipeline, PipelineSnapshot
from src.runner.services.runs import finish_run_failed, finish_run_success, start_run
from src.runner.services.sql_full import run_sql_full_pipeline
from src.runner.services.sql_incremental import run_sql_incremental_pipeline

logger = logging.getLogger("etl_runner")

MAX_ATTEMPTS = 3
BACKOFF_SECONDS = (1, 2, 4)


async def _get_pipeline_status(session: AsyncSession, pipeline_id: str) -> str:
    res = await session.execute(
        text("SELECT status FROM etl.etl_pipelines WHERE id = :id"),
        {"id": pipeline_id},
    )
    return res.scalar_one()


async def run_pipeline(session: AsyncSession, pipeline: EtlPipeline) -> None:
    # 1) PAUSE_REQUESTED -> PAUSED
    if pipeline.status == PipelineStatus.PAUSE_REQUESTED.value:
        await apply_pause_requested(session, pipeline.id)
        return

    # 2) RUN_REQUESTED -> RUNNING (claim)
    if pipeline.status == PipelineStatus.RUN_REQUESTED.value:
        claimed = await claim_run_requested(session, pipeline.id)
        if claimed is None:
            return  # другой раннер забрал

        snap: PipelineSnapshot = snapshot_pipeline(claimed)
        pid = snap.id
        pname = snap.name

        run_id = await start_run(session, pipeline_id=pid)

        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                if snap.mode == "full" and snap.type in ("SQL", "PYTHON"):
                    rows_read, rows_written = await run_sql_full_pipeline(session, snap, run_id=run_id)
                elif snap.mode == "incremental" and snap.type in ("SQL", "PYTHON"):
                    rows_read, rows_written = await run_sql_incremental_pipeline(session, snap, run_id=run_id)
                else:
                    raise ValueError(f"Unsupported pipeline: type={snap.type!r}, mode={snap.mode!r}")

                await finish_run_success(
                    session=session,
                    run_id=run_id,
                    rows_read=int(rows_read),
                    rows_written=int(rows_written),
                )

                # если пайплайн уже PAUSED (pause обработали внутри sql_*), не трогаем
                status = await _get_pipeline_status(session, pid)
                if status != PipelineStatus.PAUSED.value:
                    await set_status(session, pid, PipelineStatus.IDLE.value)

                return

            except Exception as exc:
                if is_db_disconnect(exc):
                    logger.warning(
                        "DB disconnected during pipeline execution. Exit tick; recovery will handle stuck RUNNING. "
                        "id=%s name=%s attempt=%d/%d err=%r",
                        pid, pname, attempt, MAX_ATTEMPTS, exc,
                    )
                    return

                await session.rollback()

                if attempt < MAX_ATTEMPTS:
                    delay = BACKOFF_SECONDS[min(attempt - 1, len(BACKOFF_SECONDS) - 1)]
                    logger.warning(
                        "Pipeline id=%s name=%s attempt %d/%d FAILED: %r. Retrying in %ss",
                        pid, pname, attempt, MAX_ATTEMPTS, exc, delay,
                    )
                    await asyncio.sleep(delay)
                    continue

                err_text = repr(exc)
                logger.error(
                    "Pipeline id=%s name=%s attempt %d/%d окончательно FAILED: %s",
                    pid, pname, attempt, MAX_ATTEMPTS, err_text,
                )
                await finish_run_failed(session=session, run_id=run_id, error_message=err_text)
                await set_status(session, pid, PipelineStatus.FAILED.value)
                raise

    # 3) если уже RUNNING — не трогаем
    if pipeline.status == PipelineStatus.RUNNING.value:
        logger.info("Skip pipeline %s: already RUNNING", pipeline.id)
        return

    return
