from __future__ import annotations

import importlib
import inspect
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypeAlias

RowIn: TypeAlias = Mapping[str, Any]
RowOut: TypeAlias = dict[str, Any]

TransformFn: TypeAlias = Callable[[Sequence[RowIn]], Any]


def load_python_transform(dotted_path: str) -> TransformFn:
    """
    dotted_path: 'src.pipelines.some_task' where module exports transform(rows)
    transform can be sync/async.
    """
    mod = importlib.import_module(dotted_path)
    fn = getattr(mod, "transform", None)
    if fn is None:
        raise ValueError(f"Python task module {dotted_path!r} must export transform(rows)")
    return fn


async def apply_transform(fn: TransformFn, rows: Sequence[RowIn]) -> list[RowOut]:
    res = fn(rows)
    if inspect.isawaitable(res):
        res = await res

    return [dict(r) for r in res]
