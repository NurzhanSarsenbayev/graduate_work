from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline
from src.runner.orchestration.executor import PipelineExecutor
from src.runner.repos.pipelines import PipelinesRepo
from src.runner.services.db_errors import is_db_disconnect
from src.runner.services.pipeline_snapshot import (
    PipelineSnapshot, snapshot_pipeline_with_tasks)
from src.runner.orchestration.executor import short_db_error

logger = logging.getLogger("etl_runner")


class PipelineDispatcher:
    """Orchestrates a single pipeline execution:
    pause/claim/retry/execution/final status."""

    def __init__(
        self,
        *,
        executor: PipelineExecutor,
        pipelines: PipelinesRepo,
        max_attempts: int = 3,
        backoff_seconds: tuple[float, ...] = (1, 2, 4),
    ) -> None:
        self._executor = executor
        self._pipelines = pipelines
        self._max_attempts = max_attempts
        self._backoff_seconds = backoff_seconds

    async def dispatch(
            self,
            session: AsyncSession,
            pipeline: EtlPipeline) -> None:
        # 1) PAUSE_REQUESTED -> PAUSED
        if pipeline.status == PipelineStatus.PAUSE_REQUESTED.value:
            await self._pipelines.apply_pause_requested(session, pipeline.id)
            return

        # 2) RUN_REQUESTED -> RUNNING (claim)
        if pipeline.status == PipelineStatus.RUN_REQUESTED.value:
            claimed = await self._pipelines.claim_run_requested(
                session, pipeline.id)
            if claimed is None:
                return  # claimed by another runner

            snap: PipelineSnapshot = await snapshot_pipeline_with_tasks(
                session, claimed)
            logger.info("Pipeline snapshot: id=%s tasks=%d",
                        snap.id, len(snap.tasks))
            pid = snap.id
            pname = snap.name

            for attempt in range(1, self._max_attempts + 1):
                try:
                    await self._executor.execute(session, snap, attempt=attempt)

                    status = await self._pipelines.get_status(session, pid)

                    # If someone already paused it (or requested pause
                    # and it was applied elsewhere) — don't touch.
                    if status == PipelineStatus.PAUSED.value:
                        return

                    # Otherwise finalize ONLY if still RUNNING (conditional!)
                    ok = await self._pipelines.finish_running_to_idle(session, pid)
                    if not ok:
                        logger.info(
                            "Skip finalization to IDLE for pipeline"
                            " id=%s: status changed concurrently",
                            pid,
                        )
                    return

                except Exception as exc:
                    if is_db_disconnect(exc):
                        logger.warning(
                            "DB disconnected during pipeline execution."
                            " Exit tick; recovery will handle stuck RUNNING. "
                            "id=%s name=%s attempt=%d/%d err=%r",
                            pid, pname, attempt, self._max_attempts, exc,
                        )
                        return

                    if attempt < self._max_attempts:
                        delay = self._backoff_seconds[
                            min(attempt - 1, len(self._backoff_seconds) - 1)
                        ]
                        logger.warning(
                            "Pipeline id=%s name=%s "
                            "attempt %d/%d FAILED: %r. Retrying in %ss",
                            pid, pname, attempt,
                            self._max_attempts, short_db_error(exc), delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.error(
                        "Pipeline id=%s name=%s"
                        " attempt %d/%d FAILED permanently: %r",
                        pid, pname, attempt, self._max_attempts, short_db_error(exc),
                    )
                    await self._pipelines.fail_if_active(session, pid)

                    raise

        # 3) If already RUNNING — do not touch it
        if pipeline.status == PipelineStatus.RUNNING.value:
            logger.info("Skip pipeline %s: already RUNNING", pipeline.id)
            return

        return
