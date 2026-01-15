from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ======================
#   Base models
# ======================

class PipelineBase(BaseModel):
    """Common fields used for creating/reading a pipeline (without id and status)."""

    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    type: str = "SQL"          # "SQL" / "PYTHON"
    mode: str = "full"         # "full" / "incremental"
    enabled: bool = True
    target_table: str
    batch_size: int = 1000


class PipelineCreate(PipelineBase):
    """Request model for creating a pipeline."""

    source_query: str
    python_module: str | None = None

    # incremental
    incremental_key: str | None = None
    incremental_id_key: str | None = None  # NEW


class PipelineUpdate(BaseModel):
    """Request model for partial pipeline updates."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    type: str | None = None
    mode: str | None = None
    enabled: bool | None = None
    target_table: str | None = None
    batch_size: int | None = None
    source_query: str | None = None

    python_module: str | None = None

    # incremental
    incremental_key: str | None = None
    incremental_id_key: str | None = None  # NEW


# ======================
#   Response models
# ======================

class PipelineOut(PipelineBase):
    """Simplified pipeline representation returned by the API."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    status: str
    python_module: str | None = None
    source_query: str | None = None

    # incremental
    incremental_key: str | None = None
    incremental_id_key: str | None = None  # NEW


class PipelineRunOut(BaseModel):
    """Model used for pipeline run history responses."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None = None
    rows_read: int
    rows_written: int
    error_message: str | None = None
