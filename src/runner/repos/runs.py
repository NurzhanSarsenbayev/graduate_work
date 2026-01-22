from __future__ import annotations

import logging
from uuid import uuid4

from sqlalchemy import insert, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import RunStatus
from src.app.models import EtlRun
from src.runner.services.time_utils import utcnow_naive

logger = logging.getLogger("etl_runner")


class RunsRepo:
    async def start_run(
            self,
            session: AsyncSession,
            *,
            pipeline_id: str) -> str:
        run_id = str(uuid4())
        stmt = insert(EtlRun).values(
            id=run_id,
            pipeline_id=pipeline_id,
            status=RunStatus.RUNNING.value,
            started_at=utcnow_naive(),
            rows_read=0,
            rows_written=0,
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("Started ETL run id=%s pipeline_id=%s",
                    run_id,
                    pipeline_id)
        return run_id

    async def finish_success(
        self,
        session: AsyncSession,
        *,
        run_id: str,
        rows_read: int,
        rows_written: int,
    ) -> None:
        stmt = (
            update(EtlRun)
            .where(EtlRun.id == run_id)
            .values(
                status=RunStatus.SUCCESS.value,
                finished_at=utcnow_naive(),
                rows_read=rows_read,
                rows_written=rows_written,
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.info("Finished ETL run id=%s SUCCESS (read=%d written=%d)",
                    run_id, rows_read, rows_written)

    async def finish_failed(
        self,
        session: AsyncSession,
        *,
        run_id: str,
        error_message: str,
    ) -> None:
        stmt = (
            update(EtlRun)
            .where(EtlRun.id == run_id)
            .values(
                status=RunStatus.FAILED.value,
                finished_at=utcnow_naive(),
                error_message=error_message[:1000],
            )
        )
        await session.execute(stmt)
        await session.commit()
        logger.error("ETL run id=%s FAILED: %s", run_id, error_message[:300])

    async def recover_running_failed_bulk(
            self,
            session: AsyncSession,
            pipeline_ids: list[str]) -> int:
        if not pipeline_ids:
            return 0
        await session.execute(
            update(EtlRun)
            .where(EtlRun.pipeline_id.in_(pipeline_ids))
            .where(EtlRun.status == RunStatus.RUNNING.value)
            .values(
                status=RunStatus.FAILED.value,
                finished_at=utcnow_naive(),
                error_message="recovered after runner crash",
            )
        )
        await session.commit()
        return len(pipeline_ids)
