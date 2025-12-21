from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline
from src.runner.orchestration.executor import PipelineExecutor
from src.runner.repos.pipelines import PipelinesRepo
from src.runner.services.db_errors import is_db_disconnect
from src.runner.services.pipeline_snapshot import PipelineSnapshot, snapshot_pipeline

logger = logging.getLogger("etl_runner")


class PipelineDispatcher:
    """Оркестрация одного пайплайна: pause/claim/retry/execution/final status."""

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

    async def dispatch(self, session: AsyncSession, pipeline: EtlPipeline) -> None:
        # 1) PAUSE_REQUESTED -> PAUSED
        if pipeline.status == PipelineStatus.PAUSE_REQUESTED.value:
            await self._pipelines.apply_pause_requested(session, pipeline.id)
            return

        # 2) RUN_REQUESTED -> RUNNING (claim)
        if pipeline.status == PipelineStatus.RUN_REQUESTED.value:
            claimed = await self._pipelines.claim_run_requested(session, pipeline.id)
            if claimed is None:
                return  # другой раннер забрал

            snap: PipelineSnapshot = snapshot_pipeline(claimed)
            pid = snap.id
            pname = snap.name

            for attempt in range(1, self._max_attempts + 1):
                try:
                    await self._executor.execute(session, snap)

                    # если пайплайн уже PAUSED (pause обработали внутри sql_*), не трогаем
                    status = await self._pipelines.get_status(session, pid)
                    if status != PipelineStatus.PAUSED.value:
                        await self._pipelines.set_status(session, pid, PipelineStatus.IDLE.value)

                    return

                except Exception as exc:
                    if is_db_disconnect(exc):
                        logger.warning(
                            "DB disconnected during pipeline execution. Exit tick; recovery will handle stuck RUNNING. "
                            "id=%s name=%s attempt=%d/%d err=%r",
                            pid, pname, attempt, self._max_attempts, exc,
                        )
                        return

                    if attempt < self._max_attempts:
                        delay = self._backoff_seconds[
                            min(attempt - 1, len(self._backoff_seconds) - 1)
                        ]
                        logger.warning(
                            "Pipeline id=%s name=%s attempt %d/%d FAILED: %r. Retrying in %ss",
                            pid, pname, attempt, self._max_attempts, exc, delay,
                        )
                        await asyncio.sleep(delay)
                        continue

                    logger.error(
                        "Pipeline id=%s name=%s attempt %d/%d окончательно FAILED: %r",
                        pid, pname, attempt, self._max_attempts, exc,
                    )
                    raise

        # 3) если уже RUNNING — не трогаем
        if pipeline.status == PipelineStatus.RUNNING.value:
            logger.info("Skip pipeline %s: already RUNNING", pipeline.id)
            return

        return
