from __future__ import annotations

from datetime import datetime
from typing import Optional, List

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


class EtlPipeline(Base):
    """Описание ETL-пайплайна (etl.etl_pipelines)."""

    __tablename__ = "etl_pipelines"
    __table_args__ = (
        {"schema": "etl"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )
    name: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # "SQL" / "PYTHON"
    type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Базовый SQL-источник для SQL-пайплайнов (может быть NULL для PYTHON)
    source_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    target_table: Mapped[str] = mapped_column(Text, nullable=False)

    # "full" / "incremental"
    mode: Mapped[str] = mapped_column(Text, nullable=False)

    incremental_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    batch_size: Mapped[int] = mapped_column(Integer, nullable=False, default=1000)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # "IDLE" / "RUNNING" / "PAUSED" / "FAILED"
    status: Mapped[str] = mapped_column(Text, nullable=False, default="IDLE")

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
    tasks: Mapped[List["EtlPipelineTask"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )
    state: Mapped[Optional["EtlState"]] = relationship(
        back_populates="pipeline",
        uselist=False,
        cascade="all, delete-orphan",
    )
    runs: Mapped[List["EtlRun"]] = relationship(
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('SQL', 'PYTHON')",
            name="etl_pipelines_type_check",
        ),
        CheckConstraint(
            "mode IN ('full', 'incremental')",
            name="etl_pipelines_mode_check",
        ),
        CheckConstraint(
            "status IN ('IDLE', 'RUNNING', 'PAUSED', 'FAILED')",
            name="etl_pipelines_status_check",
        ),
        {"schema": "etl"},
    )


class EtlPipelineTask(Base):
    """Шаг пайплайна (etl.etl_pipeline_tasks)."""

    __tablename__ = "etl_pipeline_tasks"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "order_index", name="etl_pipeline_tasks_order_uq"),
        {"schema": "etl"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    pipeline_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
        nullable=False,
    )

    order_index: Mapped[int] = mapped_column(Integer, nullable=False)

    # "SQL" / "PYTHON"
    task_type: Mapped[str] = mapped_column(Text, nullable=False)

    # Для SQL: текст SQL; для PYTHON: имя зарегистрированной задачи
    body: Mapped[str] = mapped_column(Text, nullable=False)

    source_table: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_table: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    pipeline: Mapped["EtlPipeline"] = relationship(back_populates="tasks")

    __table_args__ = (
        CheckConstraint(
            "task_type IN ('SQL', 'PYTHON')",
            name="etl_pipeline_tasks_type_check",
        ),
        UniqueConstraint("pipeline_id", "order_index", name="etl_pipeline_tasks_order_uq"),
        {"schema": "etl"},
    )


class EtlState(Base):
    """Состояние пайплайна (checkpoint) — etl.etl_state."""

    __tablename__ = "etl_state"
    __table_args__ = (
        {"schema": "etl"},
    )

    pipeline_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
        primary_key=True,
    )

    last_processed_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_processed_value: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    pipeline: Mapped["EtlPipeline"] = relationship(back_populates="state")


class EtlRun(Base):
    """История запусков (etl.etl_runs)."""

    __tablename__ = "etl_runs"
    __table_args__ = (
        {"schema": "etl"},
    )

    id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        primary_key=True,
        server_default=func.gen_random_uuid(),
    )

    pipeline_id: Mapped[str] = mapped_column(
        UUID(as_uuid=False),
        ForeignKey("etl.etl_pipelines.id", ondelete="CASCADE"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    rows_read: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    rows_written: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # "RUNNING" / "SUCCESS" / "FAILED"
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="RUNNING",
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pipeline: Mapped["EtlPipeline"] = relationship(back_populates="runs")

    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="etl_runs_status_check",
        ),
        {"schema": "etl"},
    )
