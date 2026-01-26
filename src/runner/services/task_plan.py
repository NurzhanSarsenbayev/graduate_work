from __future__ import annotations

from src.app.core.constants import is_allowed_target
from src.runner.services.pipeline_snapshot import PipelineSnapshot


def validate_tasks_v1(p: PipelineSnapshot) -> PipelineSnapshot:
    if not p.tasks:
        return p

    tasks_sorted = tuple(sorted(p.tasks, key=lambda t: t.order_index))

    # uniqueness + basic fields
    seen: set[int] = set()
    for t in tasks_sorted:
        if t.order_index in seen:
            raise ValueError(f"Duplicate task " f"order_index={t.order_index} in pipeline={p.id}")
        seen.add(t.order_index)

        if not t.task_type or not t.task_type.strip():
            raise ValueError(
                f"Task task_type is empty" f" (pipeline={p.id} order_index={t.order_index})"
            )

        if not t.body or not t.body.strip():
            raise ValueError(
                f"Task body is empty" f" (pipeline={p.id} order_index={t.order_index})"
            )

    # v1: first must be SQL
    if tasks_sorted[0].task_type != "SQL":
        raise ValueError("Tasks v1 require first" " task_type='SQL' (single reader)")

    # v1: rest must be PYTHON
    for t in tasks_sorted[1:]:
        if t.task_type != "PYTHON":
            raise ValueError("Tasks v1 allow only PYTHON after first SQL task")

    # v1: only last task may override target_table (keep it simple)
    for t in tasks_sorted[:-1]:
        if t.target_table is not None:
            raise ValueError(
                "Tasks v1: target_table override is allowed"
                " only on the last task "
                f"(pipeline={p.id} order_index={t.order_index})"
            )

    final_target = tasks_sorted[-1].target_table or p.target_table
    if not is_allowed_target(final_target):
        raise ValueError(f"Target not allowed: {final_target!r}" f" (pipeline={p.id})")

    # return normalized (sorted) snapshot
    from dataclasses import replace

    return replace(p, tasks=tasks_sorted)
