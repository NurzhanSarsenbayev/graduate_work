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
from src.runner.services.writers import write_target_table

logger = logging.getLogger("etl_runner")


async def run_sql_full_pipeline(
    session: AsyncSession,
    pipeline: EtlPipeline,
) -> None:
    """Один полный прогон SQL-пайплайна в режиме full."""

    if pipeline.type != "SQL":
        raise ValueError(f"Unsupported pipeline.type: {pipeline.type}")
    if pipeline.mode != "full":
        raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode}")
    if not pipeline.source_query:
        raise ValueError("Pipeline has empty source_query")

    logger.info(
        "Running ETL for pipeline id=%s name=%s mode=%s target=%s",
        pipeline.id,
        pipeline.name,
        pipeline.mode,
        pipeline.target_table,
    )

    run = await start_run(session, pipeline)

    rows_read = 0
    rows_written = 0

    try:
        # 1. Читаем данные из источника
        src_result = await session.execute(text(pipeline.source_query))
        rows = src_result.mappings().all()
        rows_read = len(rows)

        logger.info(
            "Pipeline id=%s name=%s: read %d rows from source",
            pipeline.id,
            pipeline.name,
            rows_read,
        )

        # 2. Пишем в целевую таблицу
        if rows:
            rows_written = await write_target_table(session, pipeline, rows)

        # 3. Успешное завершение
        await finish_run_success(
            session=session,
            pipeline=pipeline,
            run=run,
            rows_read=rows_read,
            rows_written=rows_written,
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
