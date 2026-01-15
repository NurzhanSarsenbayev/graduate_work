from __future__ import annotations

import logging

from sqlalchemy import text

from src.app.core.enums import PipelineStatus
from src.runner.adapters.transformers import resolve_transformer
from src.runner.adapters.writers import resolve_writer
from src.runner.ports.pipeline import PipelineLike
from src.runner.orchestration.context import ExecutionContext

logger = logging.getLogger("etl_runner")


def _wrap_query_with_limit_offset(
        base_query: str,
        limit: int,
        offset: int) -> str:
    q = base_query.strip().rstrip(";")
    return f"SELECT * FROM ({q}) AS src LIMIT {limit} OFFSET {offset}"


async def _pause_if_requested(
    ctx: ExecutionContext,
    pipeline_id: str,
) -> bool:
    status = await ctx.pipelines.get_status(ctx.session, pipeline_id)
    if status == PipelineStatus.PAUSE_REQUESTED.value:
        await ctx.pipelines.apply_pause_requested(
            ctx.session, pipeline_id)  # commit inside
        logger.info("Pause requested:"
                    " pipeline id=%s -> PAUSED (after batch)", pipeline_id)
        return True
    return False


async def run_sql_full_pipeline(
    ctx: ExecutionContext,
    pipeline: PipelineLike,
) -> tuple[int, int]:
    session = ctx.session

    if pipeline.type not in ("SQL", "PYTHON", "ES"):
        raise ValueError(f"Unsupported pipeline.type: {pipeline.type}")
    if pipeline.mode != "full":
        raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode}")
    if not pipeline.source_query:
        raise ValueError("Pipeline has empty source_query")

    batch_size = int(pipeline.batch_size or 1000)
    offset = 0

    logger.info(
        "Running ETL full: id=%s name=%s type=%s target=%s batch_size=%s",
        pipeline.id,
        pipeline.name,
        pipeline.type,
        pipeline.target_table,
        batch_size,
    )

    total_read = 0
    total_written = 0

    transformer = resolve_transformer(pipeline)
    writer = resolve_writer(pipeline)

    while True:
        batch_query = _wrap_query_with_limit_offset(
            pipeline.source_query, batch_size, offset)
        src_result = await session.execute(text(batch_query))
        rows = src_result.mappings().all()

        if not rows:
            break

        total_read += len(rows)

        rows = await transformer.transform(pipeline, rows)

        if rows:
            written = await writer.write(session, pipeline, rows)
            total_written += int(written or 0)

        await session.commit()

        if await _pause_if_requested(ctx, pipeline.id):
            return total_read, total_written

        offset += batch_size

    return total_read, total_written
