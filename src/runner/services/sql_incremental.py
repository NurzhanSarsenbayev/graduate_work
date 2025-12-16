from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models import EtlState
from src.app.core.enums import PipelineStatus
from src.runner.services.pipeline_control import apply_pause_requested
from src.runner.services.transformers import resolve_transformer
from src.runner.services.writers import resolve_writer

logger = logging.getLogger("etl_runner")


def _pget(pipeline: Any, key: str, default: Any = None) -> Any:
    """Достаём поле из snapshot-а, который может быть dict или dataclass/obj."""
    if isinstance(pipeline, dict):
        return pipeline.get(key, default)
    return getattr(pipeline, key, default)


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


async def _pause_if_requested(session: AsyncSession, pipeline_id: str) -> bool:
    res = await session.execute(
        text("SELECT status FROM etl.etl_pipelines WHERE id = :id"),
        {"id": pipeline_id},
    )
    status = res.scalar_one()
    if status == PipelineStatus.PAUSE_REQUESTED.value:
        await apply_pause_requested(session, pipeline_id)  # commit внутри
        logger.info("Pause requested: pipeline id=%s -> PAUSED (after batch)", pipeline_id)
        return True
    return False


async def run_sql_incremental_pipeline(
    session: AsyncSession,
    pipeline: Any,  # dict или PipelineSnapshot
    *,
    run_id: str,  # сейчас может не использоваться — ок
) -> tuple[int, int]:
    """Incremental прогон SQL/PYTHON пайплайна.

    pipeline: snapshot (dict или dataclass/obj).
    Возвращаем (rows_read, rows_written).
    """

    ptype = _pget(pipeline, "type")
    mode = _pget(pipeline, "mode")

    if ptype not in ("SQL", "PYTHON"):
        raise ValueError(f"Unsupported pipeline.type: {ptype}")
    if mode != "incremental":
        raise ValueError(f"Unsupported pipeline.mode: {mode}")

    source_query = _pget(pipeline, "source_query")
    if not source_query:
        raise ValueError("Pipeline has empty source_query")

    inc_key = _pget(pipeline, "incremental_key")
    if not inc_key:
        raise ValueError("Incremental pipeline requires incremental_key")

    batch_size = int(_pget(pipeline, "batch_size") or 1000)

    # ✅ убрали хардкод: tie-breaker можно задать, иначе fallback на film_id
    id_key = (_pget(pipeline, "incremental_id_key") or "film_id").strip()

    pid = str(_pget(pipeline, "id"))
    pname = str(_pget(pipeline, "name") or pid)

    total_read = 0
    total_written = 0

    transformer = resolve_transformer(pipeline)  # если resolve_* ждут EtlPipeline и упадут — скажи
    writer = resolve_writer(pipeline)

    try:
        state = await _get_state(session, pid)
        last_ts_raw = state.last_processed_value if state and state.last_processed_value else None
        last_id = state.last_processed_id if state and state.last_processed_id else None

        last_ts = datetime.fromisoformat(last_ts_raw) if last_ts_raw else None

        logger.info(
            "INC start: pipeline=%s batch_size=%s inc_key=%s id_key=%s last_ts=%s last_id=%s",
            pname, batch_size, inc_key, id_key, last_ts, last_id,
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
                params = {"last_ts": last_ts, "last_id": last_id, "limit": batch_size}

            res = await session.execute(text(batch_sql), params)
            src_rows = res.mappings().all()

            logger.info("INC batch fetched: pipeline=%s rows=%d", pname, len(src_rows))

            if not src_rows:
                logger.info("INC done: pipeline=%s (no more rows)", pname)
                break

            total_read += len(src_rows)

            # transform
            rows = await transformer.transform(pipeline, src_rows)

            # write
            if rows:
                written = await writer.write(session, pipeline, rows)
                total_written += int(written or 0)

            # ✅ checkpoint берём по исходному src_rows, а не по transform (надёжнее)
            tail = src_rows[-1]

            if inc_key not in tail:
                raise ValueError(f"Row does not contain incremental_key={inc_key!r}")
            if id_key not in tail:
                raise ValueError(f"Row does not contain incremental_id_key={id_key!r}")

            last_ts = tail[inc_key]
            last_id = str(tail[id_key])

            logger.info(
                "INC checkpoint update: pipeline=%s -> last_ts=%s last_id=%s",
                pname, last_ts, last_id,
            )

            await _upsert_state(session, pid, last_ts.isoformat(), last_id)

            await session.commit()

            if await _pause_if_requested(session, pid):
                return total_read, total_written

        return total_read, total_written

    except Exception:
        logger.exception("Incremental pipeline failed id=%s name=%s", pid, pname)
        raise
