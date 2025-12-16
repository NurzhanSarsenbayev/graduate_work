from __future__ import annotations

from enum import Enum


class PipelineStatus(str, Enum):
    IDLE = "IDLE"
    RUN_REQUESTED = "RUN_REQUESTED"
    RUNNING = "RUNNING"
    PAUSE_REQUESTED = "PAUSE_REQUESTED"
    PAUSED = "PAUSED"
    FAILED = "FAILED"


class RunStatus(str, Enum):
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
