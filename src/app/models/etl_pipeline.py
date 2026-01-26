from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Integer,
    Text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.app.core.enums import PipelineStatus

from .base import Base

if TYPE_CHECKING:
    from src.app.models.etl_pipeline_task import EtlPipelineTask
    from src.app.models.etl_run import EtlRun
    from src.app.models.etl_state import EtlState


class EtlPipeline(Base):
    """ETL pipeline definition (etl.etl_pipelines)."""

    __tablename__ = "etl_pipelines"
    __table_args__ = (
        CheckConstraint(
            "type IN ('SQL', 'PYTHON', 'ES')",
            name="etl_pipelines_type_check",
        ),
        CheckConstraint(
            "mode IN ('full', 'incremental')",
            name="etl_pipelines_mode_check",
        ),
        CheckConstraint(
            "status IN ('IDLE','RUN_REQUESTED',"
            " 'RUNNING', 'PAUSE_REQUESTED', 'PAUSED', 'FAILED')",
            name="etl_pipelines_status_check",
        ),
        {"schema": "etl"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Pipeline type: "SQL" / "PYTHON"
    type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="SQL",
    )

    # Base SQL source for SQL pipelines (may be NULL for PYTHON)
    source_query: Mapped[str | None] = mapped_column(Text, nullable=True)

    # For PYTHON pipelines: dotted import path to a module with transform()
    python_module: Mapped[str | None] = mapped_column(Text, nullable=True)

    target_table: Mapped[str] = mapped_column(Text, nullable=False)

    # Execution mode: "full" / "incremental"
    mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="full",
    )

    incremental_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    incremental_id_key: Mapped[str | None] = mapped_column(Text, nullable=True)

    batch_size: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=1000,
    )
    enabled: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )

    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=PipelineStatus.IDLE.value,
    )

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relations
    tasks: Mapped[list[EtlPipelineTask]] = relationship(
        "EtlPipelineTask",
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )
    state: Mapped[EtlState | None] = relationship(
        "EtlState",
        back_populates="pipeline",
        uselist=False,
        cascade="all, delete-orphan",
    )
    runs: Mapped[list[EtlRun]] = relationship(
        "EtlRun",
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )
