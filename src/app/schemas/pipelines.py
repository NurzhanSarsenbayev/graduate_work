from __future__ import annotations

import re
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

IDENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

PipelineType = Literal["SQL", "PYTHON", "ES"]
PipelineMode = Literal["full", "incremental"]


class PipelineBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    description: str | None = None
    type: PipelineType = "SQL"
    mode: PipelineMode = "full"
    enabled: bool = True
    target_table: str
    batch_size: int = 1000

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = v.strip()
        if not (3 <= len(v) <= 64):
            raise ValueError("name must be 3..64 characters")
        if not NAME_RE.fullmatch(v):
            raise ValueError("name must match [A-Za-z0-9_-]")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int) -> int:
        if not (1 <= v <= 50_000):
            raise ValueError("batch_size must be 1..50000")
        return v


class PipelineCreate(PipelineBase):
    source_query: str
    python_module: str | None = None

    incremental_key: str | None = None
    incremental_id_key: str | None = None

    @field_validator("incremental_key", "incremental_id_key")
    @classmethod
    def validate_sql_identifiers(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not IDENT_RE.fullmatch(v):
            raise ValueError("must be a valid SQL identifier")
        return v

    @field_validator("python_module")
    @classmethod
    def validate_python_module(cls, v: str | None) -> str | None:
        if v == "":
            return None
        if v is None:
            return v
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.]+", v):
            raise ValueError("python_module contains invalid characters")
        if not v.startswith("src.pipelines.python_tasks."):
            raise ValueError("python_module must be under src.pipelines.python_tasks.*")
        return v

    @model_validator(mode="after")
    def validate_business_rules(self):
        if self.mode == "incremental":
            q = self.source_query.lower()

            # very lightweight contract check (not a SQL parser)
            if self.incremental_key and self.incremental_key.lower() not in q:
                raise ValueError("source_query must include incremental_key in SELECT output")

            if self.incremental_id_key and self.incremental_id_key.lower() not in q:
                raise ValueError("source_query must include incremental_id_key in SELECT output")

            if not self.incremental_key or not self.incremental_id_key:
                raise ValueError("incremental mode requires incremental_key and incremental_id_key")
        if self.type == "PYTHON":
            if not self.python_module:
                raise ValueError("PYTHON pipelines require python_module")
        return self


class PipelineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    description: str | None = None
    type: PipelineType | None = None
    mode: PipelineMode | None = None
    enabled: bool | None = None
    target_table: str | None = None
    batch_size: int | None = None
    source_query: str | None = None

    python_module: str | None = None

    incremental_key: str | None = None
    incremental_id_key: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, v: str | None) -> str | None:
        if v == "":
            return None
        if v is None:
            return v
        v = v.strip()
        if not (3 <= len(v) <= 64):
            raise ValueError("name must be 3..64 characters")
        if not NAME_RE.fullmatch(v):
            raise ValueError("name must match [A-Za-z0-9_-]")
        return v

    @field_validator("batch_size")
    @classmethod
    def validate_batch_size(cls, v: int | None) -> int | None:
        if v is None:
            return v
        if not (1 <= v <= 50_000):
            raise ValueError("batch_size must be 1..50000")
        return v

    @field_validator("incremental_key", "incremental_id_key")
    @classmethod
    def validate_sql_identifiers(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not IDENT_RE.fullmatch(v):
            raise ValueError("must be a valid SQL identifier")
        return v

    @field_validator("python_module")
    @classmethod
    def validate_python_module(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.strip()
        if not re.fullmatch(r"[A-Za-z0-9_.]+", v):
            raise ValueError("python_module contains invalid characters")
        if not v.startswith("src.pipelines.python_tasks."):
            raise ValueError("python_module must be under src.pipelines.python_tasks.*")
        return v


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
