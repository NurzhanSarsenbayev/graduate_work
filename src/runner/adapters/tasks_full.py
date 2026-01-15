from __future__ import annotations

import logging
from dataclasses import replace

from sqlalchemy import text

from src.app.core.enums import PipelineStatus
from src.app.core.constants import is_allowed_target
from src.runner.adapters.tasks_python import (
    apply_transform, load_python_transform)
from src.runner.adapters.writers import resolve_writer
from src.runner.orchestration.context import ExecutionContext
from src.runner.services.pipeline_snapshot import PipelineSnapshot

logger = logging.getLogger("etl_runner")


def _wrap_query_with_limit_offset(
        base_query: str,
        limit: int,
        offset: int) -> str:
    q = base_query.strip().rstrip(";")
    return f"SELECT * FROM ({q}) AS src LIMIT {limit} OFFSET {offset}"


async def _pause_if_requested(ctx: ExecutionContext, pipeline_id: str) -> bool:
    status = await ctx.pipelines.get_status(ctx.session, pipeline_id)
    if status == PipelineStatus.PAUSE_REQUESTED.value:
        await ctx.pipelines.apply_pause_requested(
            ctx.session, pipeline_id)  # commit inside
        logger.info("Pause requested: "
                    "pipeline id=%s -> PAUSED (after batch)",
                    pipeline_id)
        return True
    return False


async def run_tasks_full(
        ctx: ExecutionContext,
        p: PipelineSnapshot) -> tuple[int, int]:
    if not p.tasks:
        raise ValueError("Tasks runner requires non-empty tasks")

    session = ctx.session

    reader_sql = p.tasks[0].body
    batch_size = int(p.batch_size or 1000)
    offset = 0

    final_target = p.tasks[-1].target_table or p.target_table

    if not is_allowed_target(final_target):
        raise ValueError(f"Task-level target_table"
                         f" is not allowed: {final_target!r}")

    p_view = replace(p, source_query=reader_sql, target_table=final_target)

    writer = resolve_writer(p_view)

    py_fns = [load_python_transform(t.body) for t in p.tasks[1:]]

    total_read = 0
    total_written = 0

    logger.info(
        "TASKS FULL start: pipeline=%s batch_size=%s steps=%d target=%s",
        p.name, batch_size, len(p.tasks), final_target,
    )

    while True:
        batch_query = _wrap_query_with_limit_offset(
            reader_sql, batch_size, offset)
        res = await session.execute(text(batch_query))
        rows = res.mappings().all()

        if not rows:
            break

        total_read += len(rows)

        for fn in py_fns:
            rows = await apply_transform(fn, rows)
            if not rows:
                break

        if rows:
            written = await writer.write(session, p_view, rows)
            total_written += int(written or 0)

        await session.commit()

        if await _pause_if_requested(ctx, p.id):
            return total_read, total_written

        offset += batch_size

    return total_read, total_written
