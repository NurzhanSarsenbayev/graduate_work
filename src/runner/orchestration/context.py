from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from src.runner.repos.pipelines import PipelinesRepo
from src.runner.repos.runs import RunsRepo
from src.runner.repos.state import StateRepo


@dataclass(frozen=True, slots=True)
class ExecutionContext:
    session: AsyncSession
    run_id: str
    runs: RunsRepo
    pipelines: PipelinesRepo
    state: StateRepo
