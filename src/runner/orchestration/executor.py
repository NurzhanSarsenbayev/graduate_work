from __future__ import annotations

import os
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from src.runner.adapters.sql_full import run_sql_full_pipeline
from src.runner.adapters.sql_incremental import run_sql_incremental_pipeline
from src.runner.adapters.tasks_full import run_tasks_full
from src.runner.adapters.tasks_incremental import run_tasks_incremental
from src.runner.services.task_plan import validate_tasks_v1
from src.runner.orchestration.context import ExecutionContext
from src.runner.ports.pipeline import PipelineLike
from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo
from src.runner.repos.state import StateRepo
from src.runner.services.db_errors import is_db_disconnect
from src.runner.services.logctx import ctx_prefix

LOG_TRACEBACKS = os.getenv("ETL_LOG_TRACEBACKS", "0") == "1"
logger = logging.getLogger("etl_runner")

ERROR_CAP = 2000


def _cap(s: str, limit: int = ERROR_CAP) -> str:
    s = s.strip()
    return s if len(s) <= limit else s[:limit] + "...(truncated)"


def short_db_error(exc: Exception) -> str:
    orig = getattr(exc, "orig", None)
    if orig is not None:
        return f"{type(orig).__name__}: {orig}"
    return str(exc).split("[SQL:", 1)[0].strip()[:200]


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    rows_read: int
    rows_written: int


RunnerFn = Callable[[ExecutionContext, PipelineLike], Awaitable[tuple[int, int]]]


class PipelineExecutor:
    def __init__(self, *, runs: RunsRepo, pipelines: PipelinesRepo, state: StateRepo) -> None:
        self._runs = runs
        self._pipelines = pipelines
        self._state = state
        self._strategies: dict[str, RunnerFn] = {
            "full": run_sql_full_pipeline,
            "incremental": run_sql_incremental_pipeline,
        }

    async def execute(
        self,
        session: AsyncSession,
        pipeline: PipelineLike,
        *,
        attempt: int | None = None,
    ) -> ExecutionResult:
        pid = str(pipeline.id)
        pname = str(getattr(pipeline, "name", pid))

        run_id = await self._runs.start_run(session, pipeline_id=pid)
        ctx_str = ctx_prefix(pid=pid, pname=pname, rid=str(run_id), attempt=attempt)

        logger.info("%s run started", ctx_str)

        ctx = ExecutionContext(
            session=session,
            run_id=run_id,
            runs=self._runs,
            pipelines=self._pipelines,
            state=self._state,
        )

        try:
            rows_read, rows_written = await self._run_body(ctx, pipeline)

            await self._runs.finish_success(
                session,
                run_id=run_id,
                rows_read=int(rows_read),
                rows_written=int(rows_written),
            )

            logger.info("%s run finished SUCCESS read=%d written=%d",
                        ctx_str,
                        int(rows_read),
                        int(rows_written))
            return ExecutionResult(rows_read=int(rows_read), rows_written=int(rows_written))

        except Exception as exc:
            if is_db_disconnect(exc):
                logger.warning(
                    "DB disconnected during execution."
                    " Leaving pipeline RUNNING for recovery. %s err=%s",
                    ctx_str,
                    short_db_error(exc),
                )
                raise

            logger.error("Execution failed: %s err=%s",
                         ctx_str, short_db_error(exc))

            if LOG_TRACEBACKS:
                logger.exception("Execution traceback: %s",
                                 ctx_str)

            await session.rollback()

            err_text = _cap(f"{type(exc).__name__}: {short_db_error(exc)}")
            await self._runs.finish_failed(session,
                                           run_id=run_id,
                                           error_message=err_text)

            raise

    async def _run_body(self, ctx: ExecutionContext, pipeline: PipelineLike) -> tuple[int, int]:
        tasks = getattr(pipeline, "tasks", ())
        if tasks:
            snap = validate_tasks_v1(pipeline)  # type: ignore[arg-type]
            if snap.mode == "full":
                return await run_tasks_full(ctx, snap)
            if snap.mode == "incremental":
                return await run_tasks_incremental(ctx, snap)
            raise ValueError(f"Unsupported pipeline.mode: {snap.mode!r}")

        runner = self._strategies.get(pipeline.mode)
        if runner is None:
            raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode!r}")
        return await runner(ctx, pipeline)
