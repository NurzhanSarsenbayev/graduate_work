from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from . import EtlPipeline
from .base import Base


class EtlPipelineTask(Base):
    """Шаг пайплайна (etl.etl_pipeline_tasks)."""

    __tablename__ = "etl_pipeline_tasks"
    __table_args__ = (
        # порядок шагов уникален в рамках одного пайплайна
        UniqueConstraint(
            "pipeline_id",
            "order_index",
            name="etl_pipeline_tasks_order_uq",
        ),
        CheckConstraint(
            "task_type IN ('SQL', 'PYTHON')",
            name="etl_pipeline_tasks_type_check",
        ),
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

    pipeline: Mapped["EtlPipeline"] = relationship(
        "EtlPipeline",
        back_populates="tasks",
    )
