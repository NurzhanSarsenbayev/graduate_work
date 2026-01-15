
# Tasks Model (v1)

This document describes the **Tasks v1** execution model for the Fault-Tolerant ETL Platform.

Tasks v1 extends the pipeline model by allowing a pipeline to be defined as a **linear execution plan**, rather than a single monolithic `source_query`.

This is an intentionally constrained MVP — not a full workflow DSL.

---

## Motivation

The original pipeline model used a single SQL query as the source.

Tasks v1 was introduced to:

- Separate **data extraction** (SQL) from **transformations** (Python)
- Reuse the existing pipeline infrastructure (state, runs, recovery)
- Prepare the architecture for future extensibility (branching, multiple readers, etc.)
- Avoid building a full workflow engine prematurely

Tasks v1 is a controlled execution model, not an orchestration framework.

---

## Conceptual Model

A pipeline with tasks looks like this:

```

[ SQL Reader ] → [ Python Transform ] → [ Python Transform ] → Writer

````

Rules:

- Exactly one **reader**
- Zero or more **transforms**
- One **writer**, inferred from the final target

---

## Storage Model

### Table: `etl.etl_pipeline_tasks`

```sql
CREATE TABLE etl.etl_pipeline_tasks (
    id           uuid PRIMARY KEY,
    pipeline_id  uuid NOT NULL REFERENCES etl.etl_pipelines(id),
    order_index  int  NOT NULL,
    task_type    text NOT NULL,   -- SQL | PYTHON
    body         text NOT NULL,   -- SQL query or python dotted path
    target_table text NULL        -- override target (only allowed for the last task)
);
````

---

## Relationship to Pipelines

* `etl_pipelines` describes the **pipeline as a whole**
* `etl_pipeline_tasks` describes the **execution plan**

If a pipeline has tasks defined:

* `source_query` is ignored
* Execution is delegated to the `tasks_*` runners

---

## Snapshot Model

The runtime uses immutable snapshot objects.

```python
@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    id: str
    order_index: int
    task_type: str        # SQL | PYTHON
    body: str             # query / dotted path
    target_table: str | None

@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    id: str
    name: str
    type: str
    mode: str             # full | incremental
    batch_size: int
    source_query: str | None
    python_module: str | None
    target_table: str
    incremental_key: str | None
    incremental_id_key: str | None
    description: str | None
    tasks: tuple[TaskSnapshot, ...]
```

Snapshots decouple execution from ORM and guarantee consistency during a run.

---

## Tasks v1 Contract

All validation is performed by `validate_tasks_v1()` before execution begins.

---

### 1. Ordering

* `order_index` must be unique
* Tasks are sorted by `order_index`
* Gaps are allowed (`1, 10, 20`)

Ordering is semantic, not positional.

---

### 2. Task Types

* The **first task** must be `SQL`
* All subsequent tasks must be `PYTHON`

Forbidden:

* Python as the first step
* SQL after the first step
* Any other task types

This ensures a single source of truth for incremental cursoring.

---

### 3. `body` Semantics

* Must be non-empty
* For `SQL`: raw SQL query
* For `PYTHON`: dotted import path to a function with signature:

```python
def transform(rows: list[dict]) -> list[dict]:
    ...
```

Example:

```python
src.pipelines.python_tasks.normalize_title
```

---

### 4. Target Override (v1 Simplification)

* `target_table` may only be defined on the **last task**
* Intermediate tasks are forbidden from modifying the target

Final target resolution:

```python
final_target = last_task.target_table or pipeline.target_table
```

---

### 5. Target Allowlist

The final resolved target must pass the allowlist.

```python
def is_allowed_target(target: str) -> bool:
    if target in ALLOWED_TARGET_TABLES:
        return True
    if target.startswith("es:"):
        return target[3:] in ALLOWED_ES_INDEXES
    return False
```

Any unknown target results in a validation error.

---

## Execution Flow

### Strategy Selection

```python
if pipeline.tasks:
    snap = validate_tasks_v1(pipeline)
    run_tasks_full() / run_tasks_incremental()
else:
    run_sql_full() / run_sql_incremental()
```

---

## Tasks Full Execution

Algorithm:

1. SQL reader → `LIMIT / OFFSET`
2. Apply Python transforms sequentially
3. Write batch via writer
4. Commit
5. Check pause flag
6. Repeat

---

## Tasks Incremental Execution

Differences:

* Uses `(incremental_key, incremental_id_key)`
* Reader SQL is wrapped:

```sql
SELECT * FROM (reader_sql) src
WHERE (inc_key > last_ts)
   OR (inc_key = last_ts AND id_key > last_id)
ORDER BY inc_key, id_key
LIMIT :batch
```

* Checkpoint is derived from **reader rows**, not transformed rows

---

### Guarantees

* Second run without source changes → `read = 0`
* After touching a single row → `read = 1`

This ensures deterministic replay and cursor safety.

---

## Pause / Resume Semantics

* `PAUSE_REQUESTED` is checked **between batches**
* State is persisted via `etl_state`
* `/run` resumes from the last committed checkpoint

---

## Intentional Limitations (v1)

The following are **not supported**:

* Multiple readers
* Branching / DAGs
* Conditionals
* Parallel tasks
* Fan-out / fan-in

These are MVP constraints, not missing features.

---

## Future Extensions (v2 Ideas)

* Multiple readers
* SQL → SQL transforms
* Task-level retry/backoff
* Branching
* Visual task graph

---

## TL;DR

Tasks v1 provides:

* ✅ Single SQL reader
* ✅ Python transforms
* ✅ Full + incremental execution
* ✅ Pause / resume
* ✅ PostgreSQL + Elasticsearch sinks
* ❌ No DAGs
* ❌ No parallelism
* ❌ No workflow magic

This is a deliberate, safety-first execution model.

---

## Summary

Tasks v1 extends the pipeline model without turning the system into a workflow engine.

It preserves:

* Deterministic execution
* Recoverability
* Simplicity
* Safety

While enabling:

* Composable transformations
* Cleaner separation of concerns
* Future extensibility
