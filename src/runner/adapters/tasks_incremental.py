from __future__ import annotations

import logging
from dataclasses import replace
from datetime import datetime
from typing import Any

from sqlalchemy import text

from src.app.core.constants import is_allowed_target
from src.app.core.enums import PipelineStatus
from src.runner.adapters.tasks_python import apply_transform, load_python_transform
from src.runner.adapters.writers import resolve_writer
from src.runner.orchestration.context import ExecutionContext
from src.runner.services.pipeline_snapshot import PipelineSnapshot

logger = logging.getLogger("etl_runner")


async def _pause_if_requested(ctx: ExecutionContext, pipeline_id: str) -> bool:
    status = await ctx.pipelines.get_status(ctx.session, pipeline_id)
    if status == PipelineStatus.PAUSE_REQUESTED.value:
        await ctx.pipelines.apply_pause_requested(ctx.session, pipeline_id)  # commit inside
        logger.info("Pause requested:" " pipeline id=%s -> PAUSED (after batch)", pipeline_id)
        return True
    return False


async def run_tasks_incremental(ctx: ExecutionContext, p: PipelineSnapshot) -> tuple[int, int]:
    if not p.tasks:
        raise ValueError("Tasks runner requires non-empty tasks")
    if p.mode != "incremental":
        raise ValueError(
            f"Tasks incremental runner requires pipeline.mode='incremental', got {p.mode!r}"
        )

    session = ctx.session
    state_repo = ctx.state

    inc_key = p.incremental_key
    if not inc_key:
        raise ValueError("Incremental tasks pipeline requires incremental_key")

    id_key = (p.incremental_id_key or "film_id").strip()
    batch_size = int(p.batch_size or 1000)

    pid = str(p.id)
    pname = str(p.name or pid)

    reader_sql = p.tasks[0].body.strip().rstrip(";")
    final_target = p.tasks[-1].target_table or p.target_table

    if not is_allowed_target(final_target):
        raise ValueError(f"Task-level target_table is not allowed: {final_target!r}")

    p_view = replace(p, source_query=reader_sql, target_table=final_target)

    writer = resolve_writer(p_view)
    py_fns = [load_python_transform(t.body) for t in p.tasks[1:]]

    total_read = 0
    total_written = 0

    state = await state_repo.get(session, pid)
    last_ts_raw = state.last_processed_value if state and state.last_processed_value else None
    last_id: str | None = state.last_processed_id if state and state.last_processed_id else None

    last_ts: datetime | None = datetime.fromisoformat(last_ts_raw) if last_ts_raw else None
    if last_ts is not None and last_id is None:
        raise ValueError("Incremental state is missing last_processed_id")

    logger.info(
        "TASKS INC start: pipeline=%s batch_size=%s inc_key=%s"
        " id_key=%s last_ts=%s last_id=%s steps=%d target=%s",
        pname,
        batch_size,
        inc_key,
        id_key,
        last_ts,
        last_id,
        len(p.tasks),
        final_target,
    )

    while True:
        params: dict[str, Any] = {"limit": batch_size}

        if last_ts is None:
            batch_sql = f"""
            SELECT * FROM ({reader_sql}) AS src
            ORDER BY src.{inc_key}, src.{id_key}
            LIMIT :limit
            """
        else:
            batch_sql = f"""
            SELECT * FROM ({reader_sql}) AS src
            WHERE (src.{inc_key} > :last_ts)
               OR (src.{inc_key} = :last_ts AND src.{id_key} > :last_id)
            ORDER BY src.{inc_key}, src.{id_key}
            LIMIT :limit
            """
            params["last_ts"] = last_ts
            params["last_id"] = last_id

        res = await session.execute(text(batch_sql), params)

        src_rows_rm = res.mappings().all()
        src_rows: list[dict[str, Any]] = [dict(r) for r in src_rows_rm]

        logger.info("TASKS INC batch fetched: pipeline=%s rows=%d", pname, len(src_rows))

        if not src_rows:
            logger.info("TASKS INC done: pipeline=%s (no more rows)", pname)
            break

        total_read += len(src_rows)

        rows: list[dict[str, Any]] = src_rows
        for fn in py_fns:
            rows = await apply_transform(fn, rows)
            if not rows:
                break

        if rows:
            written = await writer.write(session, p_view, rows)
            total_written += int(written or 0)

        tail = src_rows[-1]
        if inc_key not in tail:
            raise ValueError(f"Row does not contain incremental_key={inc_key!r}")
        if id_key not in tail:
            raise ValueError(f"Row does not contain incremental_id_key={id_key!r}")

        next_last_ts_any = tail[inc_key]
        next_last_id = str(tail[id_key])

        if next_last_ts_any is None:
            raise ValueError("Invariant broken: incremental_key value is None in tail row")
        if not isinstance(next_last_ts_any, datetime):
            raise ValueError(
                f"Invariant broken: incremental_key must "
                f"be datetime, got {type(next_last_ts_any)!r}"
            )

        last_ts = next_last_ts_any
        last_id = next_last_id

        await state_repo.upsert(session, pid, last_value=last_ts.isoformat(), last_id=last_id)
        await session.commit()

        if await _pause_if_requested(ctx, pid):
            return total_read, total_written

    return total_read, total_written
