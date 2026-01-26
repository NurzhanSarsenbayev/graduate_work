
# Architecture

This document describes the architecture of the **Fault-Tolerant ETL Platform** — a platform prototype designed for building reliable, resumable, and idempotent data pipelines with explicit separation between control-plane and data-plane.

---

## Overview

The platform is designed to build analytical data marts and search indexes from operational data sources.

Primary sinks:
- PostgreSQL (`analytics.*`)
- Elasticsearch (`es:<index>`)

Key design principles:
- Explicit state machine
- Failure recovery by default
- Batch-based execution
- Idempotent writes
- Clear separation of responsibilities

---

## Design Goals

The system is designed to solve common reliability problems in real-world ETL systems:

1. **Resumability**
   Pipelines must be able to resume from the last consistent checkpoint.

2. **Idempotency**
   Re-running a pipeline should not corrupt or duplicate data.

3. **Operational Safety**
   Partial writes, inconsistent state, and undefined transitions are not allowed.

4. **Observability & Control**
   Pipelines must be externally controllable (run / pause / resume).

5. **Extensibility**
   New sinks, execution modes, and orchestration strategies should be pluggable.

---

## System Components

```

Client
|
v
ETL API (FastAPI) ──► Postgres (etl schema)
▲
|
ETL Runner (worker)
|
+------+------------------+
|                         |
Postgres (analytics)   Elasticsearch

```

### Components

#### ETL API (Control-plane)
- Manages pipeline configuration
- Validates user input
- Controls lifecycle transitions (run, pause)
- Does not execute pipelines

#### ETL Runner (Data-plane)
- Executes pipelines
- Applies retry and backoff policies
- Maintains execution state
- Implements recovery logic

#### PostgreSQL
Used as:
- Source storage
- Analytics storage
- Metadata and state storage

#### Elasticsearch
Used as:
- Search/index sink
- Feature store for downstream services

---

## Control-plane vs Data-plane

### Control-plane

Responsibilities:
- Pipeline CRUD
- State transition requests
- Validation
- Security constraints
- Configuration persistence

The control-plane never touches data.

---

### Data-plane

Responsibilities:
- Data extraction
- Transformation
- Batch execution
- Sink writes
- Recovery and retry logic

The data-plane does not expose HTTP and does not accept user input directly.

---

## Pipeline Execution Model

Pipelines can be defined in two ways:

1. **Legacy mode** — single SQL source query
2. **Tasks mode (v1)** — linear execution plan

If tasks are defined, they override the legacy mode.

---

## Tasks Model (v1)

Tasks define a **linear execution plan** inside a pipeline.

Example:

```

[ SQL Reader ] → [ Python Transform ] → [ Python Transform ] → Sink

```

### v1 Constraints (Intentional MVP Scope)

- Tasks are strictly sequential
- First step must be an SQL reader
- All subsequent steps are Python transforms
- No DAGs, no branching, no parallelism
- Each pipeline is a single execution unit

This is not a workflow engine.
It is a controlled, extensible execution plan.

---

## Incremental vs Full Execution

### Full Pipelines
- Process the entire dataset
- Used for backfills and recomputation

### Incremental Pipelines
- Resume from the last processed checkpoint
- Use explicit cursor-based pagination
- Persist progress in `etl_state`
- Commit state after every batch

Checkpointing is based on the **SQL reader output**, not on post-transform data.
This guarantees deterministic replays.

---

## Failure Handling & Recovery

The system is designed to be safe by default.

### Guarantees

- No partial writes
- No duplicate records
- Safe retries
- Resume after crash

### Mechanisms

- Explicit state machine
- Batch-level checkpointing
- Automatic retries (3 attempts)
- Exponential backoff: 1s → 2s → 4s
- Idempotent write semantics

---

## Pause / Resume Semantics

Pause requests are applied **between batches**.

A running batch is always completed safely before pausing.

This guarantees:
- No partial batches
- No inconsistent checkpoints

---

## Idempotency Model

### PostgreSQL Sink
- Implemented via UPSERT semantics

### Elasticsearch Sink
- Implemented via bulk `update` + `doc_as_upsert=true`

This allows safe replays and retries.

---

## State Machine

Pipelines are managed using an explicit state machine.

States:

- `IDLE`
- `RUN_REQUESTED`
- `RUNNING`
- `PAUSE_REQUESTED`
- `PAUSED`
- `FAILED`

Transitions:

```

IDLE -> RUN_REQUESTED -> RUNNING -> IDLE
RUNNING -> PAUSE_REQUESTED -> PAUSED
PAUSED -> RUN_REQUESTED -> RUNNING
RUNNING -> FAILED

```

Runner performs atomic claim:
`RUN_REQUESTED -> RUNNING`

This prevents concurrent execution by multiple workers.

---

## Execution Orchestration

Execution is structured as a layered orchestration:

```

Manager → Dispatcher → Executor → Adapters

```

### Manager
- Selects candidate pipelines
- Creates isolated DB sessions
- Prevents cascading failures

### Dispatcher
- Routes by pipeline status
- Applies retry + backoff
- Distinguishes business errors vs infra errors

### Executor
- Chooses execution strategy (full/incremental)
- Handles `etl_runs`
- Finalizes pipeline status
- Delegates to adapters

### Adapters
- Implement actual ETL logic
- Isolated from orchestration
- Pluggable by design

---

## Security Constraints

Targets are strictly whitelisted.

### PostgreSQL
Only predefined `analytics.*` tables are allowed.

### Elasticsearch
Only predefined indexes are allowed.

This prevents accidental or malicious writes to arbitrary destinations.

---

## Extensibility

The architecture is designed to support:

- New sinks (ClickHouse, S3, etc.)
- Python-based pipelines
- External orchestration (Airflow, Temporal, etc.)
- Parallel execution
- DAG-based task plans

The control-plane remains stable.

---

## Trade-offs

### What is intentionally missing (MVP scope)

- DAG execution
- Parallel task execution
- Scheduling
- Metrics
- DLQ

These features are intentionally postponed to keep the core system understandable and verifiable.

---

## Limitations

- Single execution unit per pipeline
- Sequential task execution
- Polling-based orchestration

These are conscious MVP constraints.

---

## Roadmap

- DAG-based execution plans
- Parallelism
- Scheduling
- Metrics (Prometheus)
- Dead Letter Queues
- Additional sinks (S3, ClickHouse)

---

## Summary

This architecture is designed to prioritize:

- Reliability over raw throughput
- Explicitness over magic
- Safety over convenience

It is intended as a platform foundation, not as a one-off ETL script.

```
