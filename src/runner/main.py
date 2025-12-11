from __future__ import annotations
from uuid import uuid4
from datetime import datetime, timezone

import asyncio
import logging
from typing import NoReturn

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, text

from src.app.models import EtlPipeline, EtlRun
from src.app.db import async_session_factory


logger = logging.getLogger("etl_runner")

def utcnow_naive() -> datetime:
    """UTC-время без tzinfo, чтобы ложилось в TIMESTAMP WITHOUT TIME ZONE."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
    # или просто datetime.utcnow(), если больше нравится

def setup_logging() -> None:
    """Базовая настройка логов для раннера."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [runner] %(message)s",
    )

async def _check_db_connection() -> None:
    """Проверка, что до БД можно достучаться."""
    async with async_session_factory() as session:  # type: AsyncSession
        # Простой ping: SELECT 1
        result = await session.execute(text("SELECT 1"))
        _ = result.scalar_one()
        logger.info("DB connection OK")

async def _get_active_pipelines(session: AsyncSession) -> list[EtlPipeline]:
    """Вернуть пайплайны, которые нужно исполнять сейчас.

    Пока супер-просто:
    - enabled = TRUE
    - status = 'RUNNING'
    """
    stmt = (
        select(EtlPipeline)
        .where(EtlPipeline.enabled.is_(True))
        .where(EtlPipeline.status == "RUNNING")
        .order_by(EtlPipeline.name)
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())

async def _run_pipeline_once(session: AsyncSession, pipeline: EtlPipeline) -> None:
    """Один полный прогон пайплайна в режиме full (без батчей).

    Ожидаем, что:
    - pipeline.type == 'SQL'
    - pipeline.mode == 'full'
    - для разных target_table разные поля в source_query:
        * analytics.film_dim:
            film_id, title, rating
        * analytics.film_rating_agg:
            film_id, avg_rating, rating_count, updated_at
    """
    logger.info(
        "Running ETL for pipeline id=%s name=%s mode=%s target=%s",
        pipeline.id,
        pipeline.name,
        pipeline.mode,
        pipeline.target_table,
    )

    # 1. Стартуем run
    run = await _start_run(session, pipeline)

    rows_read = 0
    rows_written = 0

    try:
        # 2. Читаем данные из источника
        if not pipeline.source_query:
            raise ValueError("Pipeline has empty source_query")

        src_result = await session.execute(text(pipeline.source_query))
        rows = src_result.mappings().all()  # dict-like строки
        rows_read = len(rows)

        logger.info(
            "Pipeline id=%s name=%s: read %d rows from source",
            pipeline.id,
            pipeline.name,
            rows_read,
        )

        # 3. Пишем в целевую таблицу
        if pipeline.target_table == "analytics.film_dim":
            # Старая логика для film_dim_full — оставляем как есть
            if rows:
                insert_sql = text(
                    """
                    INSERT INTO analytics.film_dim (film_id, title, rating)
                    VALUES (:film_id, :title, :rating)
                    ON CONFLICT (film_id) DO UPDATE
                    SET
                        title = EXCLUDED.title,
                        rating = EXCLUDED.rating,
                        updated_at = NOW()
                    """
                )

                for row in rows:
                    await session.execute(
                        insert_sql,
                        {
                            "film_id": row["film_id"],
                            "title": row["title"],
                            "rating": row.get("rating"),
                        },
                    )
                    rows_written += 1

        elif pipeline.target_table == "analytics.film_rating_agg":
            # Новая логика для ratings_full → analytics.film_rating_agg
            if rows:
                insert_sql_rating = text(
                    """
                    INSERT INTO analytics.film_rating_agg (
                        film_id,
                        avg_rating,
                        rating_count,
                        updated_at
                    )
                    VALUES (
                        :film_id,
                        :avg_rating,
                        :rating_count,
                        :updated_at
                    )
                    ON CONFLICT (film_id) DO UPDATE
                    SET
                        avg_rating   = EXCLUDED.avg_rating,
                        rating_count = EXCLUDED.rating_count,
                        updated_at   = EXCLUDED.updated_at
                    """
                )

                logger.info(
                    "Pipeline id=%s name=%s: writing %d rows into analytics.film_rating_agg",
                    pipeline.id,
                    pipeline.name,
                    len(rows),
                )

                for row in rows:
                    await session.execute(
                        insert_sql_rating,
                        {
                            "film_id": row["film_id"],
                            "avg_rating": row["avg_rating"],
                            "rating_count": row["rating_count"],
                            "updated_at": row["updated_at"],
                        },
                    )
                    rows_written += 1

        else:
            # На будущее: если кто-то настроит target_table, который мы не поддерживаем
            raise ValueError(f"Unsupported target_table: {pipeline.target_table}")

        # 4. Коммитим всё и отмечаем SUCCESS
        await _finish_run_success(
            session=session,
            pipeline=pipeline,
            run=run,
            rows_read=rows_read,
            rows_written=rows_written,
        )

    except Exception as exc:
        # Откатываем незакоммиченные изменения,
        # отмечаем FAILED и логируем ошибку
        await session.rollback()
        await _finish_run_failed(
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

async def runner_tick() -> None:
    """Один тик раннера.

    Сейчас:
    - открываем сессию;
    - ищем активные пайплайны;
    - для каждого пишем лог и вызываем заглушку _run_pipeline_once.
    """
    async with async_session_factory() as session:  # type: AsyncSession
        pipelines = await _get_active_pipelines(session)

        if not pipelines:
            logger.info("No active pipelines (enabled & RUNNING) found")
            return

        logger.info("Found %d active pipeline(s)", len(pipelines))

        for pipeline in pipelines:
            try:
                await _run_pipeline_once(session, pipeline)
            except Exception:
                logger.exception(
                    "Error while running pipeline id=%s name=%s",
                    pipeline.id,
                    pipeline.name,
                )

async def _start_run(session: AsyncSession, pipeline: EtlPipeline) -> EtlRun:
    """Создать запись в etl_runs со статусом RUNNING."""
    run = EtlRun(
        id=str(uuid4()),
        pipeline_id=pipeline.id,
        status="RUNNING",
        started_at=utcnow_naive(),
        rows_read=0,
        rows_written=0,
    )
    session.add(run)
    await session.flush()  # чтобы run.id был доступен, если генерится в БД
    logger.info(
        "Started ETL run id=%s for pipeline id=%s name=%s",
        run.id,
        pipeline.id,
        pipeline.name,
    )
    return run


async def _finish_run_success(
    session: AsyncSession,
    pipeline: EtlPipeline,
    run: EtlRun,
    rows_read: int,
    rows_written: int,
) -> None:
    """Отметить успешное завершение запуска."""
    run.status = "SUCCESS"
    run.finished_at = utcnow_naive()
    run.rows_read = rows_read
    run.rows_written = rows_written

    pipeline.status = "IDLE"

    await session.commit()
    logger.info(
        "Finished ETL run id=%s for pipeline id=%s name=%s: SUCCESS (read=%d, written=%d)",
        run.id,
        pipeline.id,
        pipeline.name,
        rows_read,
        rows_written,
    )


async def _finish_run_failed(
    session: AsyncSession,
    pipeline: EtlPipeline,
    run: EtlRun,
    error_message: str,
) -> None:
    """Отметить неуспешное завершение запуска."""
    run.status = "FAILED"
    run.finished_at = utcnow_naive()
    run.error_message = error_message[:1000]  # на всякий случай обрежем

    pipeline.status = "FAILED"

    await session.commit()
    logger.error(
        "ETL run id=%s for pipeline id=%s name=%s FAILED: %s",
        run.id,
        pipeline.id,
        pipeline.name,
        error_message,
    )

async def main_loop(poll_interval: float = 5.0) -> NoReturn:
    """Основной бесконечный цикл раннера."""
    setup_logging()
    logger.info("ETL Runner starting up...")

    # Проверим соединение с БД один раз на старте
    try:
        await _check_db_connection()
    except Exception:
        logger.exception("DB connection failed on startup")
        # Жёстко не падаем, но логируем
    else:
        logger.info("Startup checks passed")

    logger.info("Entering main loop with poll_interval=%s seconds", poll_interval)

    while True:
        try:
            await runner_tick()
        except Exception:
            logger.exception("Error during runner tick")
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    asyncio.run(main_loop())
