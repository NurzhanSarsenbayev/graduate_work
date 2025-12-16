from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline
from src.runner.services.pipeline_control import (
    apply_pause_requested,
    claim_run_requested,
    set_status,
)
from src.runner.services.sql_full import run_sql_full_pipeline
from src.runner.services.sql_incremental import run_sql_incremental_pipeline

async def run_pipeline(session: AsyncSession, pipeline: EtlPipeline) -> None:
    # 1) PAUSE_REQUESTED -> PAUSED (атомарно)
    if pipeline.status == PipelineStatus.PAUSE_REQUESTED.value:
        await apply_pause_requested(session, pipeline.id)
        return

    # 2) RUN_REQUESTED -> RUNNING (атомарно claim)
    if pipeline.status == PipelineStatus.RUN_REQUESTED.value:
        claimed = await claim_run_requested(session, pipeline.id)
        if claimed is None:
            # другой раннер уже забрал
            return

        try:
            if claimed.mode == "full" and claimed.type in ("SQL", "PYTHON"):
                await run_sql_full_pipeline(session, claimed)

            elif claimed.mode == "incremental" and claimed.type in ("SQL", "PYTHON"):
                await run_sql_incremental_pipeline(session, claimed)

            else:
                raise ValueError(
                    f"Unsupported pipeline: type={claimed.type!r}, mode={claimed.mode!r}"
                )

            await set_status(session, claimed, PipelineStatus.IDLE.value)

        except Exception:
            await set_status(session, claimed, PipelineStatus.FAILED.value)
            raise

        return

    raise ValueError(f"Unexpected pipeline status: {pipeline.status}")
