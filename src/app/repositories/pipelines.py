from __future__ import annotations

from typing import Sequence

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from src.app.models import EtlPipeline, EtlRun
from src.app.core.exceptions import PipelineNotFoundError
from src.app.core.enums import PipelineStatus


class SQLPipelinesRepository:
    """Repository for working with pipelines and runs.

    Responsibilities:
    - no business logic (storage access only);
    - compatibility with the service layer via domain exceptions;
    - consistent contract (returns an object or raises an error).
    """

    async def list_pipelines(
            self,
            session: AsyncSession) -> Sequence[EtlPipeline]:
        stmt = select(EtlPipeline).order_by(EtlPipeline.name)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_pipeline(
            self,
            session: AsyncSession,
            pipeline_id: str) -> EtlPipeline:
        stmt = select(EtlPipeline).where(EtlPipeline.id == pipeline_id)
        result = await session.execute(stmt)
        pipeline = result.scalar_one_or_none()

        if pipeline is None:
            raise PipelineNotFoundError(f"Pipeline {pipeline_id} not found")

        return pipeline

    async def create_pipeline(
            self,
            session: AsyncSession,
            payload) -> EtlPipeline:
        """Create a new ETL pipeline.

        This method does not perform business validation
        (validation must happen in the service layer).
        """

        pipeline = EtlPipeline(
            id=str(uuid4()),
            name=payload.name,
            description=payload.description,
            type=payload.type,
            mode=payload.mode,
            enabled=payload.enabled,
            batch_size=payload.batch_size,
            target_table=payload.target_table,
            source_query=payload.source_query,
            python_module=payload.python_module,
            incremental_key=payload.incremental_key,
            incremental_id_key=payload.incremental_id_key,
        )

        session.add(pipeline)
        await session.commit()
        await session.refresh(pipeline)
        return pipeline

    async def update_pipeline_status(
        self,
        session: AsyncSession,
        pipeline_id: str,
        new_status: str,
    ) -> EtlPipeline:
        pipeline = await self.get_pipeline(session, pipeline_id)
        pipeline.status = new_status

        await session.commit()
        await session.refresh(pipeline)
        return pipeline

    async def update_pipeline(
        self,
        session: AsyncSession,
        pipeline_id: str,
        data: dict,
    ) -> EtlPipeline:
        pipeline = await self.get_pipeline(session, pipeline_id)

        for field, value in data.items():
            setattr(pipeline, field, value)

        await session.commit()
        await session.refresh(pipeline)
        return pipeline

    async def list_pipeline_runs(
        self,
        session: AsyncSession,
        pipeline_id: str,
        limit: int = 50,
    ) -> Sequence[EtlRun]:

        # We intentionally do not validate pipeline existence here —
        # the service layer owns that decision (separation of concerns).

        stmt = (
            select(EtlRun)
            .where(EtlRun.pipeline_id == pipeline_id)
            .order_by(EtlRun.started_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def request_run(
            self,
            session: AsyncSession,
            pipeline_id: str) -> EtlPipeline | None:
        """Atomically move a pipeline to RUN_REQUESTED if allowed.

        Returns the updated pipeline, or None if the transition was not applied.
        """
        allowed_from = (
            PipelineStatus.IDLE.value,
            PipelineStatus.PAUSED.value,
            PipelineStatus.PAUSE_REQUESTED.value,
        )

        stmt = (
            update(EtlPipeline)
            .where(
                EtlPipeline.id == pipeline_id,
                EtlPipeline.status.in_(allowed_from),
            )
            .values(status=PipelineStatus.RUN_REQUESTED.value)
            .returning(EtlPipeline)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()
        await session.commit()

        if updated is None:
            return None

        # returning(...) usually provides an ORM object already,
        # but refresh() is a safe extra step.
        await session.refresh(updated)
        return updated

    async def request_pause(
            self,
            session: AsyncSession,
            pipeline_id: str) -> EtlPipeline | None:
        """Atomically move a pipeline to PAUSE_REQUESTED if allowed.

        Returns the updated pipeline, or None if the transition was not applied.
        """
        allowed_from = (
            PipelineStatus.RUNNING.value,
            PipelineStatus.RUN_REQUESTED.value,
            PipelineStatus.IDLE.value,
        )

        stmt = (
            update(EtlPipeline)
            .where(
                EtlPipeline.id == pipeline_id,
                EtlPipeline.status.in_(allowed_from),
            )
            .values(status=PipelineStatus.PAUSE_REQUESTED.value)
            .returning(EtlPipeline)
        )
        result = await session.execute(stmt)
        updated = result.scalar_one_or_none()
        await session.commit()

        if updated is None:
            return None

        await session.refresh(updated)
        return updated

    async def claim_run_requested(
            self,
            session: AsyncSession,
            pipeline_id: str) -> bool:
        """Runner claim step: RUN_REQUESTED -> RUNNING.

        Returns True if we claimed the pipeline.
        Returns False if it was already claimed or not in the expected state.
        """
        stmt = (
            update(EtlPipeline)
            .where(
                EtlPipeline.id == pipeline_id,
                EtlPipeline.status == PipelineStatus.RUN_REQUESTED.value,
            )
            .values(status=PipelineStatus.RUNNING.value)
        )
        result = await session.execute(stmt)
        await session.commit()
        return (result.rowcount or 0) == 1
