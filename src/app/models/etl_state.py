from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import ForeignKey, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from .base import Base


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

    pipeline: Mapped["EtlPipeline"] = relationship(
        "EtlPipeline",
        back_populates="state",
    )
