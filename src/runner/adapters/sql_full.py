from __future__ import annotations

import logging

from sqlalchemy import text

from src.runner.adapters.transformers import resolve_transformer
from src.runner.adapters.writers import resolve_writer
from src.runner.orchestration.context import ExecutionContext
from src.runner.ports.pipeline import PipelineLike
from src.runner.services.logctx import ctx_prefix
from src.runner.services.pause import _pause_if_requested

logger = logging.getLogger("etl_runner")


def _wrap_query_with_limit_offset(base_query: str, limit: int, offset: int) -> str:
    q = base_query.strip().rstrip(";")
    return f"SELECT * FROM ({q}) AS src LIMIT {limit} OFFSET {offset}"


async def run_sql_full_pipeline(
    ctx: ExecutionContext,
    pipeline: PipelineLike,
) -> tuple[int, int]:
    session = ctx.session

    pid = str(pipeline.id)
    pname = str(pipeline.name or pid)
    rid = str(ctx.run_id)
    ctx_str = ctx_prefix(pid=pid, pname=pname, rid=rid)
    batch_no = 0

    if pipeline.type not in ("SQL", "PYTHON", "ES"):
        raise ValueError(f"Unsupported pipeline.type: {pipeline.type}")
    if pipeline.mode != "full":
        raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode}")
    if not pipeline.source_query:
        raise ValueError("Pipeline has empty source_query")

    batch_size = int(pipeline.batch_size or 1000)
    offset = 0

    logger.info(
        "%s FULL start type=%s target=%s batch_size=%s",
        ctx_str,
        pipeline.type,
        pipeline.target_table,
        batch_size,
    )

    total_read = 0
    total_written = 0
    non_empty_batches = 0

    transformer = resolve_transformer(pipeline)
    writer = resolve_writer(pipeline)

    try:
        while True:
            batch_no += 1
            current_offset = offset

            logger.info("%s FULL batch=%d offset=%d", ctx_str, batch_no, current_offset)

            batch_query = _wrap_query_with_limit_offset(
                pipeline.source_query, batch_size, current_offset
            )
            src_result = await session.execute(text(batch_query))
            src_rows_rm = src_result.mappings().all()
            src_rows: list[dict[str, object]] = [dict(r) for r in src_rows_rm]

            fetched = len(src_rows)

            logger.info(
                "%s FULL batch=%d fetched rows=%d",
                ctx_str,
                batch_no,
                fetched,
            )

            if fetched == 0:
                logger.info(
                    "%s FULL done non_empty_batches=%d total_read=%d total_written=%d",
                    ctx_str,
                    non_empty_batches,
                    total_read,
                    total_written,
                )
                break

            non_empty_batches += 1

            if not src_rows:
                logger.info(
                    "%s FULL done batches=%d total_read=%d total_written=%d",
                    ctx_str,
                    batch_no,
                    total_read,
                    total_written,
                )
                break

            total_read += fetched

            rows = await transformer.transform(pipeline, src_rows)

            if rows:
                written = await writer.write(session, pipeline, rows)
                written_i = int(written or 0)
                total_written += written_i
                logger.info(
                    "%s FULL batch=%d written=%d total_written=%d",
                    ctx_str,
                    batch_no,
                    written_i,
                    total_written,
                )

            await session.commit()

            # next offset: continue after the rows we actually fetched
            offset = current_offset + fetched

            logger.info(
                "%s FULL checkpoint batch=%d next_offset=%d total_read=%d total_written=%d",
                ctx_str,
                batch_no,
                offset,
                total_read,
                total_written,
            )

            if await _pause_if_requested(ctx, pipeline.id):
                return total_read, total_written

        return total_read, total_written
    finally:
        await writer.close()
