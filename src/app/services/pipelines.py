from __future__ import annotations

from collections.abc import Sequence

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


def _validate_pipeline_config(final: dict) -> None:
    mode = final.get("mode")
    ptype = final.get("type")

    if mode == "incremental":
        if not final.get("incremental_key") or not final.get("incremental_id_key"):
            raise ValueError("incremental mode requires incremental_key and incremental_id_key")

    if ptype == "PYTHON":
        if not final.get("python_module"):
            raise ValueError("PYTHON pipelines require python_module")


class PipelinesService:
    """Service layer for managing ETL pipelines."""

    def __init__(
        self,
        session: AsyncSession,
        repo: SQLPipelinesRepository | None = None,
    ) -> None:
        self.session = session
        self.repo = repo or SQLPipelinesRepository()

    # ---------- Pipeline CRUD ----------

    async def list_pipelines(self) -> Sequence[EtlPipeline]:
        """Return all pipelines."""
        return await self.repo.list_pipelines(self.session)

    async def get_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Return a pipeline by id or raise PipelineNotFoundError."""
        try:
            return await self.repo.get_pipeline(self.session, pipeline_id)
        except PipelineNotFoundError:
            # Pass through the domain error as-is.
            raise

    async def create_pipeline(self, payload: PipelineCreate) -> EtlPipeline:
        """Create a new pipeline.

        Business rule validation (target_table, etc.) lives here.
        The repository is responsible only for persistence.
        """
        if not is_allowed_target(payload.target_table):
            raise ValueError(f"target_table '{payload.target_table}' is not allowed")

        try:
            return await self.repo.create_pipeline(self.session, payload)
        except IntegrityError as exc:
            # Roll back the transaction.
            await self.session.rollback()

            # At this level we assume the most common IntegrityError cause
            # is a duplicate pipeline name. If more unique constraints are
            # added later, we can refine this handling.
            raise PipelineNameAlreadyExistsError(
                "A pipeline with this name already exists"
            ) from exc

    # ---------- Status management ----------

    async def run_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Request a pipeline run atomically (status -> RUN_REQUESTED)."""
        # Ensure the pipeline exists.
        pipeline = await self.get_pipeline(pipeline_id)

        # Idempotency: if already RUNNING / RUN_REQUESTED, return as-is.
        if pipeline.status in (
            PipelineStatus.RUNNING.value,
            PipelineStatus.RUN_REQUESTED.value,
        ):
            return pipeline

        updated = await self.repo.request_run(self.session, pipeline_id)
        if updated is not None:
            return updated

        # If transition did not happen (e.g., FAILED), return current state.
        return await self.get_pipeline(pipeline_id)

    async def pause_pipeline(self, pipeline_id: str) -> EtlPipeline:
        """Request a pipeline pause atomically (status -> PAUSE_REQUESTED)."""
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
        """Partially update a pipeline.

        Rule:
        - if the pipeline is RUNNING, updates are not allowed.
        """
        pipeline = await self.get_pipeline(pipeline_id)

        if pipeline.status == PipelineStatus.RUNNING.value:
            raise PipelineIsRunningError("Cannot update pipeline while it is RUNNING")

        final = {
            "type": pipeline.type,
            "mode": pipeline.mode,
            "incremental_key": pipeline.incremental_key,
            "incremental_id_key": pipeline.incremental_id_key,
            "python_module": pipeline.python_module,
            **update_data,
        }
        _validate_pipeline_config(final)

        updated = await self.repo.update_pipeline(
            session=self.session,
            pipeline_id=pipeline_id,
            data=update_data,
        )
        # repo.update_pipeline either returns an object,
        # or raises its own error if something goes wrong.
        if updated is None:
            # Defensive: if repo returned None (race conditions, etc.).
            raise PipelineNotFoundError(f"Pipeline {pipeline_id} not found")

        return updated

    # ---------- Run history ----------

    async def list_pipeline_runs(
        self,
        pipeline_id: str,
        limit: int,
    ) -> Sequence[EtlRun]:
        """Return run history for a pipeline.

        If the pipeline does not exist, raise PipelineNotFoundError.
        """
        # Ensure the pipeline exists.
        await self.get_pipeline(pipeline_id)

        return await self.repo.list_pipeline_runs(
            session=self.session,
            pipeline_id=pipeline_id,
            limit=limit,
        )
