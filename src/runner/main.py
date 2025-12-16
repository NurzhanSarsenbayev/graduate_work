from __future__ import annotations

import asyncio
import logging
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.db import async_session_factory
from src.runner.services import get_active_pipelines, run_pipeline


logger = logging.getLogger("etl_runner")


def setup_logging() -> None:
    """Базовая настройка логов для раннера."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [runner] %(message)s",
    )


async def _check_db_connection() -> None:
    """Проверка, что до БД можно достучаться."""
    async with async_session_factory() as session:  # type: AsyncSession
        result = await session.execute(text("SELECT 1"))
        _ = result.scalar_one()
        logger.info("DB connection OK")


async def runner_tick() -> None:
    """Один тик раннера.

    - открываем сессию;
    - ищем активные пайплайны;
    - для каждого вызываем run_sql_full_pipeline.
    """
    async with async_session_factory() as session:  # type: AsyncSession
        pipelines = await get_active_pipelines(session)

        if not pipelines:
            logger.info("No active pipelines (enabled & RUN_REQUESTED/PAUSE_REQUESTED) found")
            return

        logger.info("Found %d active pipeline(s)", len(pipelines))

        for pipeline in pipelines:
            try:
                await run_pipeline(session, pipeline)
            except Exception:
                logger.exception(
                    "Error while running pipeline id=%s name=%s",
                    pipeline.id,
                    pipeline.name,
                )


async def main_loop(poll_interval: float = 5.0) -> NoReturn:
    """Основной бесконечный цикл раннера."""
    setup_logging()
    logger.info("ETL Runner starting up...")

    try:
        await _check_db_connection()
    except Exception:
        logger.exception("DB connection failed on startup")
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
