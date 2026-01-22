from __future__ import annotations

from typing import Sequence

from sqlalchemy import or_, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.enums import PipelineStatus
from src.app.models import EtlPipeline


class PipelinesRepo:
    async def get_active(self, session: AsyncSession) -> list[EtlPipeline]:
        stmt = (
            select(EtlPipeline)
            .where(EtlPipeline.enabled.is_(True))
            .where(
                or_(
                    EtlPipeline.status == PipelineStatus.RUN_REQUESTED.value,
                    EtlPipeline.status == PipelineStatus.PAUSE_REQUESTED.value,
                )
            )
            .order_by(EtlPipeline.name)
        )
        res = await session.execute(stmt)
        return list(res.scalars().all())

    async def get_status(self, session: AsyncSession, pipeline_id: str) -> str:
        res = await session.execute(
            text("SELECT status FROM etl.etl_pipelines WHERE id = :id"),
            {"id": pipeline_id},
        )
        return res.scalar_one()

    async def set_status(
            self,
            session: AsyncSession,
            pipeline_id: str,
            status: str) -> None:
        stmt = (
            update(EtlPipeline)
            .where(EtlPipeline.id == pipeline_id)
            .values(status=status)
        )
        await session.execute(stmt)
        await session.commit()

    async def claim_run_requested(
            self,
            session: AsyncSession,
            pipeline_id: str) -> EtlPipeline | None:
        stmt = (
            update(EtlPipeline)
            .where(EtlPipeline.id == pipeline_id)
            .where(EtlPipeline.status == PipelineStatus.RUN_REQUESTED.value)
            .values(status=PipelineStatus.RUNNING.value)
            .returning(EtlPipeline)
        )
        res = await session.execute(stmt)
        claimed = res.scalar_one_or_none()
        if claimed is not None:
            await session.commit()
        return claimed

    async def apply_pause_requested(
            self,
            session: AsyncSession,
            pipeline_id: str) -> bool:
        stmt = (
            update(EtlPipeline)
            .where(EtlPipeline.id == pipeline_id)
            .where(EtlPipeline.status == PipelineStatus.PAUSE_REQUESTED.value)
            .values(status=PipelineStatus.PAUSED.value)
        )
        res = await session.execute(stmt)
        updated = res.rowcount or 0
        if updated:
            await session.commit()
            return True
        return False

    async def list_stuck_running_ids(self, session: AsyncSession) -> list[str]:
        res = await session.execute(
            select(EtlPipeline.id).where(EtlPipeline.status
                                         == PipelineStatus.RUNNING.value)
        )
        return [row[0] for row in res.all()]

    async def mark_failed_bulk(
            self,
            session: AsyncSession,
            pipeline_ids: Sequence[str]) -> int:
        ids = list(pipeline_ids)
        if not ids:
            return 0
        await session.execute(
            update(EtlPipeline)
            .where(EtlPipeline.id.in_(ids))
            .where(EtlPipeline.status == PipelineStatus.RUNNING.value)
            .values(status=PipelineStatus.FAILED.value)
        )
        await session.commit()
        return len(ids)

    async def mark_run_requested_bulk(self, session, pipeline_ids: list[str]) -> int:
        if not pipeline_ids:
            return 0

        res = await session.execute(
            text("""
                UPDATE etl.etl_pipelines
                   SET status = :new_status
                 WHERE id = ANY(:ids)
                   AND status = :old_status
            """),
            {
                "ids": pipeline_ids,
                "new_status": PipelineStatus.RUN_REQUESTED.value,
                "old_status": PipelineStatus.RUNNING.value,
            },
        )
        return int(res.rowcount or 0)

    async def finish_running_to_idle(
            self, session: AsyncSession, pipeline_id: str
    ) -> bool:
        stmt = (
            update(EtlPipeline)
            .where(EtlPipeline.id == pipeline_id)
            .where(EtlPipeline.status == PipelineStatus.RUNNING.value)
            .values(status=PipelineStatus.IDLE.value)
        )
        res = await session.execute(stmt)
        updated = int(res.rowcount or 0)
        if updated:
            await session.commit()
            return True
        return False

    async def fail_if_active(
            self, session: AsyncSession, pipeline_id: str
    ) -> bool:
        stmt = (
            update(EtlPipeline)
            .where(EtlPipeline.id == pipeline_id)
            .where(
                EtlPipeline.status.in_(
                    [PipelineStatus.RUNNING.value, PipelineStatus.PAUSE_REQUESTED.value]
                )
            )
            .values(status=PipelineStatus.FAILED.value)
        )
        res = await session.execute(stmt)
        updated = int(res.rowcount or 0)
        if updated:
            await session.commit()
            return True
        return False