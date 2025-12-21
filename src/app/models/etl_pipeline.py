from __future__ import annotations

from datetime import datetime
from typing import Optional, List

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


class EtlPipeline(Base):
    """Описание ETL-пайплайна (etl.etl_pipelines)."""

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
            "status IN ('IDLE','RUN_REQUESTED', 'RUNNING', 'PAUSE_REQUESTED', 'PAUSED', 'FAILED')",
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
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # "SQL" / "PYTHON"
    type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="SQL",
    )

    # Базовый SQL-источник для SQL-пайплайнов (может быть NULL для PYTHON)
    source_query: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Для PYTHON пайплайнов: dotted path до модуля с transform()
    python_module: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    target_table: Mapped[str] = mapped_column(Text, nullable=False)

    # "full" / "incremental"
    mode: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="full",
    )

    # incremental: primary cursor column (обычно timestamp/updated_at)
    incremental_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # incremental: tie-breaker key (обычно film_id / id). ВАЖНО: убирает хардкод.
    incremental_id_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

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
    tasks: Mapped[List["EtlPipelineTask"]] = relationship(
        "EtlPipelineTask",
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )
    state: Mapped[Optional["EtlState"]] = relationship(
        "EtlState",
        back_populates="pipeline",
        uselist=False,
        cascade="all, delete-orphan",
    )
    runs: Mapped[List["EtlRun"]] = relationship(
        "EtlRun",
        back_populates="pipeline",
        cascade="all, delete-orphan",
    )
