from __future__ import annotations


class PipelineError(Exception):
    """Base class for exceptions in this module"""


class PipelineNotFoundError(PipelineError):
    """Pipeline with the given ID was not found."""


class PipelineIsRunningError(PipelineError):
    """Operation is not allowed while the pipeline is in RUNNING state."""


class PipelineNameAlreadyExistsError(PipelineError):
    """A pipeline with this name already exists."""
