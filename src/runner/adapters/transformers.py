from __future__ import annotations

import importlib

from dataclasses import dataclass
from typing import Protocol

from src.runner.ports.pipeline import PipelineLike

class Transformer(Protocol):
    async def transform(self, pipeline: PipelineLike, rows: list[dict]) -> list[dict]: ...


class NoOpTransformer:
    async def transform(self, pipeline: PipelineLike, rows: list[dict]) -> list[dict]:
        return rows

@dataclass(frozen=True)
class PythonCallableTransformer:
    dotted_path: str
    fn_name: str = "transform"

    async def transform(self, pipeline: PipelineLike, rows: list[dict]) -> list[dict]:
        module = importlib.import_module(self.dotted_path)
        fn = getattr(module, self.fn_name, None)
        if fn is None:
            raise ValueError(
                f"Python transformer not found: {self.dotted_path}.{self.fn_name}()"
            )

        result = fn(rows, pipeline=pipeline)
        # допускаем sync-функцию, но если вернул awaitable — поддержим
        if hasattr(result, "__await__"):
            result = await result  # type: ignore[misc]

        if not isinstance(result, list):
            raise ValueError(
                f"Python transformer must return list[dict], got {type(result)}"
            )
        return result

def resolve_transformer(pipeline: PipelineLike) -> Transformer:
    # 1) не PYTHON — просто пропускаем
    if pipeline.type != "PYTHON":
        return NoOpTransformer()

    # 2) основной (правильный) контракт
    module_path = (getattr(pipeline, "python_module", None) or "").strip()
    if module_path:
        return PythonCallableTransformer(dotted_path=module_path)

    # 3) fallback для старых пайплайнов (временно)
    desc = (pipeline.description or "").strip()
    if desc.startswith("py:"):
        legacy_path = desc.removeprefix("py:").strip()
        if legacy_path:
            return PythonCallableTransformer(dotted_path=legacy_path)

    # 4) если ничего не нашли — понятная ошибка
    raise ValueError(
        "PYTHON pipeline requires python_module. "
        "Set pipeline.python_module='src.pipelines.python_demo.demo_film_dim' "
        "or (legacy) description='py:...'"
    )