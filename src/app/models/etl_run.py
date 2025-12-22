from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import CheckConstraint, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from src.app.core.enums import RunStatus
from . import EtlPipeline
from .base import Base


class EtlRun(Base):
    """История запусков (etl.etl_runs)."""

    __tablename__ = "etl_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('RUNNING', 'SUCCESS', 'FAILED')",
            name="etl_runs_status_check",
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

    started_at: Mapped[datetime] = mapped_column(
        nullable=False,
        server_default=func.now(),
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(
        nullable=True,
    )

    rows_read: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )
    rows_written: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
    )

    # "RUNNING" / "SUCCESS" / "FAILED"
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default=RunStatus.RUNNING.value,
    )

    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    pipeline: Mapped["EtlPipeline"] = relationship(
        "EtlPipeline",
        back_populates="runs",
    )
