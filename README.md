
link:

# Fault-Tolerant ETL Platform

A platform prototype for building analytical data marts and search indexes in a distributed environment.

This system is designed for **reliable, resumable, and idempotent data pipelines** with explicit separation between
**control-plane** (management) and **data-plane** (execution).

---

## Overview

This platform allows you to:

- Define ETL pipelines via a REST API
- Execute them asynchronously in a separate worker process
- Process data in batches
- Resume after failures
- Support incremental loading
- Write results to PostgreSQL and Elasticsearch

The main design goal is **operational reliability**: pipelines should not break on transient errors, should be resumable,
and should never corrupt target data.

---

## Problem It Solves

In many real-world systems, data pipelines are:

- Fragile
- Hard to resume after failure
- Not idempotent
- Tightly coupled to their execution logic
- Difficult to observe and control

This platform addresses these issues by introducing:

- A dedicated **control-plane** for pipeline management
- A dedicated **data-plane** for execution
- Explicit state machines
- Batch-based execution
- Idempotent writes
- Pause/Resume semantics
- Automatic retries with exponential backoff

---

## Key Features

- Full and incremental SQL pipelines
- Batch-based processing
- Idempotent UPSERT semantics
- Pause / Resume between batches
- Automatic retries with exponential backoff (1s → 2s → 4s)
- Failure recovery
- REST API for pipeline management
- Docker-first setup
- Multiple sinks:
  - PostgreSQL (`analytics.*`)
  - Elasticsearch (`es:<index>`)

---

## Architecture

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

- **ETL API (Control-plane)**  
  Responsible for pipeline management, state transitions, and orchestration.

- **ETL Runner (Data-plane)**  
  A worker process that executes pipelines, handles retries, batching, and recovery.

- **PostgreSQL**  
  Used as:
  - Source
  - Analytics storage
  - Metadata and state storage

- **Elasticsearch**  
  Used as a search/indexing sink.

See `docs/ARCHITECTURE.md` for a more detailed description.

---

## Control-plane vs Data-plane

### Control-plane

- Pipeline creation
- Status management
- Validation
- Security checks
- State transitions

### Data-plane

- Data extraction
- Transformations
- Batch execution
- Writes to sinks
- Retry and recovery logic

This separation allows:

- Independent scaling
- Better fault isolation
- Clear operational boundaries

---

## Pipeline Execution Model

Pipelines can be defined in two ways:

1. **Legacy mode** — a single SQL source query
2. **Tasks mode (v1)** — a linear execution plan

If tasks are defined, they take priority over the legacy mode.

### Tasks Mode (v1) Limitations (Intentional MVP Scope)

- Tasks are executed strictly sequentially
- The first step must be an SQL reader
- All subsequent steps are Python transforms
- No DAGs, branching, or parallelism
- Each pipeline is a single execution unit

Example:

```

[ SQL Reader ] → [ Python Transform ] → Sink

````

---

## Incremental vs Full Pipelines

- **Full pipelines** process the entire dataset
- **Incremental pipelines** resume from the last processed checkpoint

Incremental execution is implemented via:

- Explicit state tracking
- Batch-based pagination
- Persistent checkpoints
- Idempotent writes

---

## Failure Handling & Recovery

This system is designed to be **operationally safe by default**.

### Guarantees

- No partial writes
- No duplicate data
- Safe retries
- Resume after crash

### Mechanisms

- Explicit pipeline states
- Batch-level checkpointing
- Automatic retries (3 attempts)
- Exponential backoff: 1s → 2s → 4s
- Idempotent UPSERT semantics

---

## Pause / Resume Semantics

Pipelines can be paused and resumed via the API.

> Important:  
> Pausing only happens **between batches**.  
> A currently running batch is always completed safely.

---

## Quickstart

### 1. Prepare environment

```bash
cp .env.example .env
````

Default values work with docker-compose.

### 2. Start the system

```bash
make up
```

Health checks:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:9200
```

---

## Creating Pipelines

### SQL → PostgreSQL (Analytics Mart)

```bash
make api-create-sql-film-rating-agg \
  NAME=film_rating_agg_pg \
  BATCH=200
```

### SQL → Elasticsearch

```bash
make api-create-es-film-rating-agg \
  NAME=film_rating_agg_es \
  BATCH=200
```

---

## Running a Pipeline

```bash
make api-run ID=<pipeline_id>
```

The runner automatically picks up pipelines in `RUN_REQUESTED` state.

---

## Verifying Results

### PostgreSQL

```sql
SELECT * FROM analytics.film_rating_agg LIMIT 5;
```

### Elasticsearch

```bash
curl "http://localhost:9200/film_rating_agg/_search?size=5" | jq
```

---

## Security Constraints (MVP)

Only whitelisted targets are allowed.

PostgreSQL:

```python
ALLOWED_TARGET_TABLES = {
    "analytics.film_dim",
    "analytics.film_rating_agg",
}
```

Elasticsearch:

```python
ALLOWED_ES_INDEXES = {
    "film_dim",
    "film_rating_agg",
}
```

Any attempt to write to a non-whitelisted target is rejected by both API and Runner.

---

## Pipeline States

* `IDLE`
* `RUN_REQUESTED`
* `RUNNING`
* `PAUSE_REQUESTED`
* `PAUSED`
* `FAILED`

Retry policy:

* 3 attempts
* Exponential backoff: 1s → 2s → 4s

---

## Project Structure

```
src/
  app/        # ETL API (FastAPI)
  runner/     # ETL Runner (worker)
infra/
  docker-compose.yml
docs/
  ARCHITECTURE.md
  demo_checks.md
```

---

## Demo Scenarios

Step-by-step validation scenarios (full, incremental, tasks mode, pause/resume, Elasticsearch) are documented in:

👉 `docs/demo_checks.md`

---

## Design Decisions

* Control-plane / Data-plane separation
* Explicit state machine
* Batch-based execution
* Idempotent writes
* Minimal DAG features (intentional MVP scope)
* Whitelisted targets for safety

---

## Limitations (Current MVP Scope)

* No DAGs
* No parallel tasks
* No scheduling
* No metrics yet
* No DLQ

---

## Roadmap

* DAG-based task plans
* Parallel execution
* Scheduling (cron / Airflow integration)
* Metrics (Prometheus)
* Dead Letter Queue (DLQ)
* New sinks (S3, ClickHouse)

---

## Author

**Nurzhan Sarsenbayev**
Platform / Data Backend Engineer
Python, ETL, Distributed Systems

```
