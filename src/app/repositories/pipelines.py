from __future__ import annotations

from typing import Sequence

from sqlalchemy import select,update
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import uuid4

from src.app.models import EtlPipeline, EtlRun
from src.app.core.exceptions import PipelineNotFoundError
from src.app.core.enums import PipelineStatus

class SQLPipelinesRepository:
    """Репозиторий для работы с пайплайнами и запусками.

    Обеспечивает:
    - отсутствие бизнес-логики;
    - совместимость с сервисным слоем через доменные исключения;
    - единообразный контракт (всегда возвращает объект или кидает ошибку).
    """

    async def list_pipelines(self, session: AsyncSession) -> Sequence[EtlPipeline]:
        stmt = select(EtlPipeline).order_by(EtlPipeline.name)
        result = await session.execute(stmt)
        return result.scalars().all()

    async def get_pipeline(self, session: AsyncSession, pipeline_id: str) -> EtlPipeline:
        stmt = select(EtlPipeline).where(EtlPipeline.id == pipeline_id)
        result = await session.execute(stmt)
        pipeline = result.scalar_one_or_none()

        if pipeline is None:
            raise PipelineNotFoundError(f"Pipeline {pipeline_id} not found")

        return pipeline

    async def create_pipeline(self, session: AsyncSession, payload) -> EtlPipeline:
        """Создать новый ETL пайплайн — без бизнес-валидации (валидация должна быть в сервисе)."""

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

        # Мы не валидируем существование pipeline здесь —
        # пусть это решает сервисный слой (по SOLID)

        stmt = (
            select(EtlRun)
            .where(EtlRun.pipeline_id == pipeline_id)
            .order_by(EtlRun.started_at.desc())
            .limit(limit)
        )
        result = await session.execute(stmt)
        return result.scalars().all()

    async def request_run(self, session: AsyncSession, pipeline_id: str) -> EtlPipeline | None:
        """Атомарно перевести пайплайн в RUN_REQUESTED, если он в разрешённом статусе.
        Возвращает обновлённый объект или None, если переход не выполнен.
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

        # returning(...) обычно уже даёт объект, но refresh не повредит
        await session.refresh(updated)
        return updated

    async def request_pause(self, session: AsyncSession, pipeline_id: str) -> EtlPipeline | None:
        """Атомарно перевести пайплайн в PAUSE_REQUESTED, если он в разрешённом статусе.
        Возвращает обновлённый объект или None.
        """
        allowed_from = (
            PipelineStatus.RUNNING.value,
            PipelineStatus.RUN_REQUESTED.value,
            PipelineStatus.IDLE.value,  # опционально: чтобы можно было поставить паузу до старта
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

    async def claim_run_requested(self, session: AsyncSession, pipeline_id: str) -> bool:
        """Claim step для runner: RUN_REQUESTED -> RUNNING.
        True если мы захватили пайплайн, False если уже захвачен/не в том статусе.
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