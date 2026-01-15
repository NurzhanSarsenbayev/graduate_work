from __future__ import annotations

import importlib
import inspect
from typing import Any, Callable, Mapping, Sequence

Row = Mapping[str, Any]
TransformFn = Callable[[Sequence[Row]], Any]


def load_python_transform(dotted_path: str) -> TransformFn:
    """
    dotted_path: 'src.pipelines.some_task' where module exports transform(rows)
    transform can be sync/async.
    """
    mod = importlib.import_module(dotted_path)
    fn = getattr(mod, "transform", None)
    if fn is None:
        raise ValueError(f"Python task module {dotted_path!r}"
                         f" must export transform(rows)")
    return fn


async def apply_transform(
        fn: TransformFn,
        rows: Sequence[Row]) -> Sequence[Row]:
    res = fn(rows)
    if inspect.isawaitable(res):
        res = await res
    return res
