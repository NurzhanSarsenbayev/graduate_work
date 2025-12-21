from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.runner.adapters.sql_full import run_sql_full_pipeline
from src.runner.adapters.sql_incremental import run_sql_incremental_pipeline
from src.runner.ports.pipeline import PipelineLike
from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo
from src.runner.repos.state import StateRepo
from src.runner.services.db_errors import is_db_disconnect

logger = logging.getLogger("etl_runner")


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    rows_read: int
    rows_written: int


class PipelineExecutor:
    """Исполнение одного пайплайна (создать run -> прогнать ETL -> завершить run)."""

    def __init__(
        self,
        *,
        runs: RunsRepo,
        pipelines: PipelinesRepo,
        state: StateRepo,
    ) -> None:
        self._runs = runs
        self._pipelines = pipelines
        self._state = state

    async def execute(self, session: AsyncSession, pipeline: PipelineLike) -> ExecutionResult:
        run_id = await self._runs.start_run(session, pipeline_id=pipeline.id)

        try:
            if pipeline.mode == "full" and pipeline.type in ("SQL", "PYTHON", "ES"):
                rows_read, rows_written = await run_sql_full_pipeline(
                    session,
                    pipeline,
                    run_id=run_id,
                    pipelines_repo=self._pipelines,
                )
            elif pipeline.mode == "incremental" and pipeline.type in ("SQL", "PYTHON", "ES"):
                rows_read, rows_written = await run_sql_incremental_pipeline(
                    session,
                    pipeline,
                    run_id=run_id,
                    pipelines_repo=self._pipelines,
                    state_repo=self._state,
                )
            else:
                raise ValueError(f"Unsupported pipeline: type={pipeline.type!r}, mode={pipeline.mode!r}")

            await self._runs.finish_success(
                session,
                run_id=run_id,
                rows_read=int(rows_read),
                rows_written=int(rows_written),
            )
            return ExecutionResult(rows_read=int(rows_read), rows_written=int(rows_written))

        except Exception as exc:
            if is_db_disconnect(exc):
                logger.warning(
                    "DB disconnected during execution. Leaving pipeline RUNNING for recovery. "
                    "id=%s name=%s err=%r",
                    pipeline.id, getattr(pipeline, "name", pipeline.id), exc,
                )
                raise

            await session.rollback()

            err_text = repr(exc)
            await self._runs.finish_failed(session, run_id=run_id, error_message=err_text)
            await self._pipelines.set_status(session, pipeline.id, PipelineStatus.FAILED.value)
            raise
