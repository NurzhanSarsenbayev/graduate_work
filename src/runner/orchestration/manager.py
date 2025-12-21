from __future__ import annotations

import logging
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.runner.orchestration.dispatcher import PipelineDispatcher
from src.runner.orchestration.executor import PipelineExecutor

from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo
from src.runner.repos.state import StateRepo

from src.runner.services.db_errors import is_db_disconnect

logger = logging.getLogger("etl_runner")


@dataclass(frozen=True, slots=True)
class TickResult:
    pipelines_found: int
    pipelines_processed: int


class PipelineManager:
    """Оркестратор одного 'тика' раннера: найти кандидатов и обработать каждый в fresh-сессии."""

    def __init__(self, session_factory) -> None:
        self._session_factory = session_factory

        # repos (одни и те же инстансы на весь процесс)
        self._pipelines = PipelinesRepo()
        self._runs = RunsRepo()
        self._state = StateRepo()

        # executor + dispatcher
        self._executor = PipelineExecutor(runs=self._runs, pipelines=self._pipelines, state=self._state)
        self._dispatcher = PipelineDispatcher(
            executor=self._executor,
            pipelines=self._pipelines,
        )

    async def tick(self) -> TickResult:
        # 1) одной сессией получаем пайплайны-кандидаты
        async with self._session_factory() as session:  # type: AsyncSession
            pipelines = await self._pipelines.get_active(session)

        if not pipelines:
            logger.info("No active pipelines (enabled & RUN_REQUESTED/PAUSE_REQUESTED) found")
            return TickResult(pipelines_found=0, pipelines_processed=0)

        logger.info("Found %d active pipeline(s)", len(pipelines))

        processed = 0

        # 2) каждый pipeline — в своей fresh-сессии
        for pipeline in pipelines:
            async with self._session_factory() as session:  # type: AsyncSession
                try:
                    await self._dispatcher.dispatch(session, pipeline)
                    processed += 1
                except Exception as exc:
                    if is_db_disconnect(exc):
                        raise
                    logger.exception(
                        "Error while running pipeline id=%s name=%s",
                        getattr(pipeline, "id", "?"),
                        getattr(pipeline, "name", "?"),
                    )

        return TickResult(pipelines_found=len(pipelines), pipelines_processed=processed)
