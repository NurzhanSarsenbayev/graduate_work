from __future__ import annotations

import asyncio
import logging
from typing import NoReturn

from sqlalchemy import text

from infra.db import async_session_factory, engine
from src.runner.orchestration.manager import PipelineManager
from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo
from src.runner.services.db_errors import is_db_disconnect

logger = logging.getLogger("etl_runner")


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [runner] %(message)s",
    )


async def _check_db_connection() -> None:
    """
    Quick DB ping.

    Important: we create/close the session inside this function
    to avoid keeping a "broken" session around.
    """
    async with async_session_factory() as session:
        result = await session.execute(text("SELECT 1"))
        _ = result.scalar_one()


async def wait_for_db(
    *,
    attempts: int = 10,
    delays: tuple[float, ...] = (1, 2, 4, 8, 8, 8, 8, 8, 8, 8),
) -> None:
    """
    Wait until the DB is up. If it is not ready after `attempts`, fail.
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
            logger.warning("DB not ready (%d/%d)." " Retrying in %ss...", i, attempts, delay)
            await asyncio.sleep(delay)

    logger.exception("DB did not become ready after %d attempts", attempts)
    raise last_exc  # type: ignore[misc]


async def main_loop(poll_interval: float = 5.0) -> NoReturn:
    logger.info("ETL Runner starting up...")

    # --- startup ---
    await wait_for_db()
    logger.info("Startup checks passed")

    pipelines_repo = PipelinesRepo()
    runs_repo = RunsRepo()

    async with async_session_factory() as session:
        pipeline_ids = await pipelines_repo.list_stuck_running_ids(session)
        if pipeline_ids:
            # mark previous RUNNING runs as FAILED (honest history)
            await runs_repo.recover_running_failed_bulk(session, pipeline_ids)

            # re-queue pipelines for execution
            updated = await pipelines_repo.mark_run_requested_bulk(session, pipeline_ids)

            await session.commit()

            logger.warning(
                "Recovery: marked RUNNING runs as"
                " FAILED and re-queued pipelines RUN_REQUESTED."
                " stuck=%d updated=%d pipeline_ids=%s",
                len(pipeline_ids),
                updated,
                pipeline_ids[:10],
            )
        else:
            logger.info("No stuck RUNNING pipelines found (recovery not needed)")

    logger.info("Entering main loop with" " poll_interval=%s seconds", poll_interval)

    manager = PipelineManager(async_session_factory)

    # --- main loop ---
    while True:
        try:
            await manager.tick()
        except Exception as exc:
            if is_db_disconnect(exc):
                logger.warning("DB disconnected during tick." " Will retry next tick. err=%r", exc)

                await asyncio.sleep(1.0)
            else:
                logger.exception("Error during runner tick")
        await asyncio.sleep(poll_interval)


async def main() -> None:
    setup_logging()
    try:
        await main_loop()
    finally:
        # important: always dispose the connection pool
        logger.info("Disposing DB engine...")
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
