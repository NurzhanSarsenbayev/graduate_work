from __future__ import annotations

import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlPipeline
from src.runner.services.runs import (
    start_run,
    finish_run_success,
    finish_run_failed,
)
from src.runner.services.writers import resolve_writer
from src.runner.services.transformers import resolve_transformer

logger = logging.getLogger("etl_runner")


def _wrap_query_with_limit_offset(base_query: str, limit: int, offset: int) -> str:
    """
    Безопасно добавляем LIMIT/OFFSET к ЛЮБОМУ source_query:
    оборачиваем в подзапрос, чтобы не ломать WITH/ORDER BY и т.д.
    """
    q = base_query.strip().rstrip(";")
    return f"SELECT * FROM ({q}) AS src LIMIT {limit} OFFSET {offset}"


async def run_sql_full_pipeline(session: AsyncSession, pipeline: EtlPipeline) -> None:
    """Полный прогон SQL/PYTHON пайплайна в режиме full с батчами."""

    if pipeline.type not in ("SQL", "PYTHON"):
        raise ValueError(f"Unsupported pipeline.type: {pipeline.type}")
    if pipeline.mode != "full":
        raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode}")
    if not pipeline.source_query:
        raise ValueError("Pipeline has empty source_query")

    batch_size = int(pipeline.batch_size or 1000)
    offset = 0

    logger.info(
        "Running ETL for pipeline id=%s name=%s type=%s mode=%s target=%s batch_size=%s",
        pipeline.id,
        pipeline.name,
        pipeline.type,
        pipeline.mode,
        pipeline.target_table,
        batch_size,
    )

    run = await start_run(session, pipeline)

    total_read = 0
    total_written = 0

    transformer = resolve_transformer(pipeline)
    writer = resolve_writer(pipeline)

    try:
        while True:
            batch_query = _wrap_query_with_limit_offset(
                base_query=pipeline.source_query,
                limit=batch_size,
                offset=offset,
            )

            src_result = await session.execute(text(batch_query))
            rows = src_result.mappings().all()

            if not rows:
                break

            batch_read = len(rows)
            total_read += batch_read

            logger.info(
                "Pipeline id=%s name=%s: read batch size=%d (offset=%d)",
                pipeline.id,
                pipeline.name,
                batch_read,
                offset,
            )

            # transform
            rows = await transformer.transform(pipeline, rows)

            # write
            if rows:
                written = await writer.write(session, pipeline, rows)
                total_written += int(written or 0)

            # ✅ фиксируем батч в БД (важно для корректности и будущей PAUSE-after-batch)
            await session.commit()

            offset += batch_size

        await finish_run_success(
            session=session,
            pipeline=pipeline,
            run=run,
            rows_read=total_read,
            rows_written=total_written,
        )

    except Exception as exc:
        await session.rollback()
        await finish_run_failed(
            session=session,
            pipeline=pipeline,
            run=run,
            error_message=str(exc),
        )
        logger.exception(
            "Error while running pipeline id=%s name=%s",
            pipeline.id,
            pipeline.name,
        )
        raise
