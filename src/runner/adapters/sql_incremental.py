from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import text

from src.app.core.enums import PipelineStatus
from src.runner.adapters.transformers import resolve_transformer
from src.runner.adapters.writers import resolve_writer
from src.runner.ports.pipeline import PipelineLike
from src.runner.orchestration.context import ExecutionContext
from src.runner.services.logctx import ctx_prefix
from src.runner.services.pause import _pause_if_requested

logger = logging.getLogger("etl_runner")


async def run_sql_incremental_pipeline(
    ctx: ExecutionContext,
    pipeline: PipelineLike,
) -> tuple[int, int]:
    session = ctx.session
    state_repo = ctx.state
    ptype = pipeline.type
    mode = pipeline.mode

    if ptype not in ("SQL", "PYTHON", "ES"):
        raise ValueError(f"Unsupported pipeline.type: {ptype}")
    if mode != "incremental":
        raise ValueError(f"Unsupported pipeline.mode: {mode}")

    source_query = pipeline.source_query
    if not source_query:
        raise ValueError("Pipeline has empty source_query")

    inc_key = pipeline.incremental_key
    if not inc_key:
        raise ValueError("Incremental pipeline requires incremental_key")

    batch_size = int(pipeline.batch_size or 1000)
    id_key = (pipeline.incremental_id_key or "film_id").strip()

    pid = str(pipeline.id)
    pname = str(pipeline.name or pid)

    rid = str(ctx.run_id)
    ctx_str = ctx_prefix(pid=pid, pname=pname, rid=rid)
    batch_no = 0

    total_read = 0
    total_written = 0

    transformer = resolve_transformer(pipeline)
    writer = resolve_writer(pipeline)

    try:
        state = await state_repo.get(session, pid)
        last_ts_raw = state.last_processed_value\
            if state and state.last_processed_value else None
        last_id = state.last_processed_id\
            if state and state.last_processed_id else None

        last_ts = datetime.fromisoformat(last_ts_raw) if last_ts_raw else None

        if last_ts is not None and last_id is None:
            raise ValueError("Incremental state is missing last_processed_id")

        logger.info(
            "%s INC start batch_size=%s inc_key=%s id_key=%s last_ts=%s last_id=%s",
            ctx_str, batch_size, inc_key, id_key, last_ts, last_id,
        )

        base = str(source_query).strip().rstrip(";")

        while True:
            if last_ts is None:
                batch_sql = f"""
                SELECT * FROM ({base}) AS src
                ORDER BY src.{inc_key}, src.{id_key}
                LIMIT :limit
                """
                params = {"limit": batch_size}
            else:
                batch_sql = f"""
                SELECT * FROM ({base}) AS src
                WHERE (src.{inc_key} > :last_ts)
                   OR (src.{inc_key} = :last_ts AND src.{id_key} > :last_id)
                ORDER BY src.{inc_key}, src.{id_key}
                LIMIT :limit
                """
                params = {"last_ts": last_ts,
                          "last_id": last_id,
                          "limit": batch_size}

            res = await session.execute(text(batch_sql), params)
            src_rows = res.mappings().all()

            if not src_rows:
                logger.info("%s INC done (no more rows) batches=%d",
                            ctx_str, batch_no)
                break

            batch_no += 1
            logger.info("%s INC batch=%d fetched rows=%d",
                        ctx_str, batch_no, len(src_rows))

            total_read += len(src_rows)

            rows = await transformer.transform(pipeline, src_rows)

            if rows:
                written = await writer.write(session, pipeline, rows)
                total_written += int(written or 0)

            tail = src_rows[-1]
            if inc_key not in tail:
                raise ValueError(f"Row does not"
                                 f" contain incremental_key={inc_key!r}")
            if id_key not in tail:
                raise ValueError(f"Row does not"
                                 f" contain incremental_id_key={id_key!r}")

            last_ts = tail[inc_key]
            last_id = str(tail[id_key])

            logger.info(
                "%s INC checkpoint batch=%d -> last_ts=%s last_id=%s",
                ctx_str, batch_no, last_ts, last_id,
            )

            last_ts_str = last_ts.isoformat()\
                if hasattr(last_ts, "isoformat") else str(last_ts)
            await state_repo.upsert(
                session, pid, last_value=last_ts_str, last_id=last_id)

            await session.commit()

            if await _pause_if_requested(ctx, pid):
                return total_read, total_written

        return total_read, total_written

    except Exception:
        logger.exception("Incremental pipeline"
                         " failed id=%s name=%s", pid, pname)
        raise
