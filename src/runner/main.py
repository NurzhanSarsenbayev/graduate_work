from __future__ import annotations

import asyncio
import logging
from typing import NoReturn

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo

from src.app.db import async_session_factory

from src.runner.services.db_errors import is_db_disconnect
from src.runner.orchestration.manager import PipelineManager
logger = logging.getLogger("etl_runner")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [runner] %(message)s",
    )


async def _check_db_connection() -> None:
    """
    Быстрый ping БД. Важно: создаём/закрываем сессию внутри, чтобы не держать "битую".
    """
    async with async_session_factory() as session:  # type: AsyncSession
        result = await session.execute(text("SELECT 1"))
        _ = result.scalar_one()


async def wait_for_db(
    *,
    attempts: int = 10,
    delays: tuple[float, ...] = (1, 2, 4, 8, 8, 8, 8, 8, 8, 8),
) -> None:
    """
    Ждём пока БД поднимется. Если не поднялась за attempts — падаем.
    """
    last_exc: Exception | None = None

    for i in range(1, attempts + 1):
        try:
            await _check_db_connection()
            logger.info("DB connection OK")
            return
        except Exception as exc:
            last_exc = exc
            delay = delays[i - 1] if i - 1 < len(delays) else delays[-1]
            logger.warning("DB not ready (%d/%d). Retrying in %ss...", i, attempts, delay)
            await asyncio.sleep(delay)

    logger.exception("DB did not become ready after %d attempts", attempts)
    raise last_exc  # type: ignore[misc]


# async def runner_tick() -> None:
#     # 1) одной сессией получаем пайплайны-кандидаты
#     async with async_session_factory() as session:  # type: AsyncSession
#         pipelines = await get_active_pipelines(session)
#
#     if not pipelines:
#         logger.info("No active pipelines (enabled & RUN_REQUESTED/PAUSE_REQUESTED) found")
#         return
#
#     logger.info("Found %d active pipeline(s)", len(pipelines))
#
#     # 2) каждый pipeline — в своей fresh-сессии
#     for pipeline in pipelines:
#         async with async_session_factory() as session:  # type: AsyncSession
#             try:
#                 await run_pipeline(session, pipeline)
#             except Exception as exc:
#                 if is_db_disconnect(exc):
#                     raise
#                 logger.exception("Error while running pipeline id=%s name=%s", pipeline.id, pipeline.name)


async def main_loop(poll_interval: float = 5.0) -> NoReturn:
    setup_logging()
    logger.info("ETL Runner starting up...")

    # --- startup ---
    await wait_for_db()
    logger.info("Startup checks passed")

    pipelines_repo = PipelinesRepo()
    runs_repo = RunsRepo()

    async with async_session_factory() as session:  # type: AsyncSession
        pipeline_ids = await pipelines_repo.list_stuck_running_ids(session)
        if pipeline_ids:
            await pipelines_repo.mark_failed_bulk(session, pipeline_ids)
            await runs_repo.recover_running_failed_bulk(session, pipeline_ids)
            logger.warning("Recovered %d stuck RUNNING pipeline(s) after crash", len(pipeline_ids))
        else:
            logger.info("No stuck RUNNING pipelines found (recovery not needed)")

    logger.info("Entering main loop with poll_interval=%s seconds", poll_interval)

    manager = PipelineManager(async_session_factory)

    # --- main loop ---
    while True:
        try:
            await manager.tick()
        except Exception as exc:
            if is_db_disconnect(exc):
                logger.warning("DB disconnected during tick. Will retry next tick. err=%r", exc)
                # Можно сделать короткую паузу, чтобы не долбить DNS/DB без смысла
                await asyncio.sleep(1.0)
            else:
                logger.exception("Error during runner tick")
        await asyncio.sleep(poll_interval)


if __name__ == "__main__":
    asyncio.run(main_loop())
