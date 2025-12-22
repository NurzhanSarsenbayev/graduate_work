from __future__ import annotations

from typing import Sequence

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.constants import is_allowed_target
from src.app.core.enums import PipelineStatus
from src.app.core.exceptions import (
    PipelineIsRunningError,
    PipelineNameAlreadyExistsError,
    PipelineNotFoundError,
)
from src.app.models import EtlPipeline, EtlRun
from src.app.repositories.pipelines import SQLPipelinesRepository
from src.app.schemas.pipelines import PipelineCreate


class PipelinesService:
    """Сервисный слой для работы с ETL-пайплайнами."""

    def __init__(
        self,
        session: AsyncSession,
        repo: SQLPipelinesRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo or SQLPipelinesRepository()

    # ---------- CRUD пайплайнов ----------

    async def list_pipelines(self) -> Sequence[EtlPipeline]:
        """Вернуть все пайплайны."""
        return await self.repo.list_pipelines(self.session)

    async def get_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Вернуть пайплайн по id или бросить PipelineNotFoundError."""
        try:
            return await self.repo.get_pipeline(self.session, pipeline_id)
        except PipelineNotFoundError:
            # просто прокидываем доменную ошибку дальше
            raise

    async def create_pipeline(self, payload: PipelineCreate) -> EtlPipeline:
        """Создать новый пайплайн.

        Валидация бизнес-правил (target_table и т.п.) — здесь,
        репозиторий отвечает только за сохранение.
        """

        if not is_allowed_target(payload.target_table):
            raise ValueError(f"target_table "
                             f"'{payload.target_table}' is not allowed")

        try:
            return await self.repo.create_pipeline(self.session, payload)
        except IntegrityError as exc:
            # Откатываем транзакцию
            await self.session.rollback()

            # На этом уровне считаем,
            # что основная причина IntegrityError — дубликат имени.
            # Если потом появятся другие уникальные ограничения, можно будет
            # добавить более тонкое разруливание.
            raise PipelineNameAlreadyExistsError(
                "Pipeline with this name already exists"
            ) from exc

    # ---------- Управление статусами ----------

    async def run_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Запросить запуск пайплайна (RUN_REQUESTED) атомарно."""
        # Проверяем, что пайплайн существует
        pipeline = await self.get_pipeline(pipeline_id)

        # Идемпотентность: если уже RUNNING/RUN_REQUESTED — просто возвращаем
        if pipeline.status in (
            PipelineStatus.RUNNING.value,
            PipelineStatus.RUN_REQUESTED.value,
        ):
            return pipeline

        updated = await self.repo.request_run(self.session, pipeline_id)
        if updated is not None:
            return updated

        # Если переход не случился (например, FAILED) — возвращаем текущее
        return await self.get_pipeline(pipeline_id)

    async def pause_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Запросить паузу (PAUSE_REQUESTED) атомарно."""
        pipeline = await self.get_pipeline(pipeline_id)

        if pipeline.status in (
            PipelineStatus.PAUSED.value,
            PipelineStatus.PAUSE_REQUESTED.value,
        ):
            return pipeline

        updated = await self.repo.request_pause(self.session, pipeline_id)
        if updated is not None:
            return updated

        return await self.get_pipeline(pipeline_id)

    async def update_pipeline(
        self,
        pipeline_id: str,
        update_data: dict,
    ) -> EtlPipeline:
        """Частично обновить пайплайн.

        Правило:
        - если пайплайн в статусе RUNNING — не даём его обновлять.
        """
        pipeline = await self.get_pipeline(pipeline_id)

        if pipeline.status == PipelineStatus.RUNNING.value:
            raise PipelineIsRunningError(
                "Cannot update pipeline while it is RUNNING")

        updated = await self.repo.update_pipeline(
            session=self.session,
            pipeline_id=pipeline_id,
            data=update_data,
        )
        # repo.update_pipeline либо вернёт объект,
        # либо кинет свою ошибку, если там что-то пойдёт не так.
        if updated is None:
            # На всякий случай, если репо вернуло None (гонки и т.п.)
            raise PipelineNotFoundError(f"Pipeline {pipeline_id} not found")

        return updated

    # ---------- История запусков ----------

    async def list_pipeline_runs(
        self,
        pipeline_id: str,
        limit: int,
    ) -> Sequence[EtlRun]:
        """Вернуть историю запусков по пайплайну.

        Если пайплайна нет — логично бросить PipelineNotFoundError.
        """
        # Проверяем, что пайплайн существует
        await self.get_pipeline(pipeline_id)

        return await self.repo.list_pipeline_runs(
            session=self.session,
            pipeline_id=pipeline_id,
            limit=limit,
        )
