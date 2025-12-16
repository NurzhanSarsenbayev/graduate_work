from __future__ import annotations

import logging

from datetime import datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlPipeline, EtlState
from src.runner.services.runs import start_run, finish_run_success, finish_run_failed
from src.runner.services.transformers import resolve_transformer
from src.runner.services.writers import resolve_writer

logger = logging.getLogger("etl_runner")


async def _get_state(session: AsyncSession, pipeline_id: str) -> EtlState | None:
    return await session.get(EtlState, pipeline_id)


async def _upsert_state(
    session: AsyncSession,
    pipeline_id: str,
    last_value: str,
    last_id: str,
) -> None:
    state = await session.get(EtlState, pipeline_id)
    if state is None:
        state = EtlState(pipeline_id=pipeline_id)
        session.add(state)

    state.last_processed_value = last_value
    state.last_processed_id = last_id


async def run_sql_incremental_pipeline(session: AsyncSession, pipeline: EtlPipeline) -> None:
    if pipeline.type not in ("SQL", "PYTHON"):
        raise ValueError(f"Unsupported pipeline.type: {pipeline.type}")
    if pipeline.mode != "incremental":
        raise ValueError(f"Unsupported pipeline.mode: {pipeline.mode}")
    if not pipeline.source_query:
        raise ValueError("Pipeline has empty source_query")
    if not pipeline.incremental_key:
        raise ValueError("Incremental pipeline requires incremental_key")

    batch_size = int(pipeline.batch_size or 1000)
    inc_key = pipeline.incremental_key  # ожидаем имя поля в результирующих rows, напр. "updated_at"
    id_key = "film_id"  # MVP: tie-breaker (для film_dim). Позже сделаем конфигом.

    run = await start_run(session, pipeline)

    total_read = 0
    total_written = 0

    transformer = resolve_transformer(pipeline)
    writer = resolve_writer(pipeline)

    try:
        state = await _get_state(session, pipeline.id)
        last_ts_raw = state.last_processed_value if state and state.last_processed_value else None
        last_id = state.last_processed_id if state and state.last_processed_id else None

        last_ts = datetime.fromisoformat(last_ts_raw) if last_ts_raw else None

        logger.info(
            "INC start: pipeline=%s mode=%s batch_size=%s last_ts=%s last_id=%s",
            pipeline.name, pipeline.mode, batch_size, last_ts, last_id,
        )

        while True:
            base = pipeline.source_query.strip().rstrip(";")

            if last_ts is None:
                # первый запуск — просто читаем с начала
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
                params = {"last_ts": last_ts, "last_id": last_id, "limit": batch_size}

            res = await session.execute(text(batch_sql), params)
            rows = res.mappings().all()

            logger.info(
                "INC batch fetched: pipeline=%s rows=%d",
                pipeline.name, len(rows),
            )

            if not rows:
                logger.info("INC done: pipeline=%s (no more rows)", pipeline.name)
                break

            total_read += len(rows)

            # transform
            rows = await transformer.transform(pipeline, rows)

            # write
            if rows:
                written = await writer.write(session, pipeline, rows)
                total_written += int(written or 0)

            # обновляем state по последней строке батча (до commit)
            tail = rows[-1]
            if inc_key not in tail:
                raise ValueError(f"Row does not contain incremental_key={inc_key!r}")
            if id_key not in tail:
                raise ValueError(f"Row does not contain id_key={id_key!r} (tie-breaker)")

            last_ts = tail[inc_key]
            last_id = str(tail[id_key])

            logger.info(
                "INC checkpoint update: pipeline=%s -> last_ts=%s last_id=%s",
                pipeline.name, last_ts, last_id,
            )

            await _upsert_state(session, pipeline.id, last_ts.isoformat(), last_id)

            # фиксируем батч + state атомарно
            await session.commit()

        await finish_run_success(session, pipeline, run, total_read, total_written)

    except Exception as exc:
        await session.rollback()
        await finish_run_failed(session, pipeline, run, str(exc))
        logger.exception("Incremental pipeline failed id=%s name=%s", pipeline.id, pipeline.name)
        raise
