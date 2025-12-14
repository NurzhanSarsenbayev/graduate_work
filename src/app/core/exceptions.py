from __future__ import annotations


class PipelineError(Exception):
    """Базовая ошибка домена ETL-пайплайнов."""


class PipelineNotFoundError(PipelineError):
    """Пайплайн с указанным ID не найден."""


class PipelineIsRunningError(PipelineError):
    """Запрещено выполнять операцию над пайплайном в статусе RUNNING."""


class PipelineNameAlreadyExistsError(PipelineError):
    """Пайплайн с таким именем уже существует."""
