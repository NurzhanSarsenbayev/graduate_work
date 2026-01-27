
# Quick Demo — Fault-Tolerant ETL Platform (Postgres + Elasticsearch)

This demo shows the core features in ~5–7 minutes:

- API-driven pipeline management
- Batched execution + idempotent writes
- Incremental mode with checkpointing (`etl.etl_state`)
- Pause / resume between batches
- Retry with backoff
- Postgres and Elasticsearch sinks

> For deeper validation scenarios, see `docs/demo_checks.md`.

---

## 0) Start the stack

```bash
make build
make up
make alembic-up
make api-health
````

Optional: watch the runner logs in a separate terminal:

```bash
make logs-runner
```

---

## 1) Full load → PostgreSQL (`analytics.film_dim`)

Reset demo state:

```bash
make db-reset-demo
make db-counts
```

Create a full SQL pipeline:

```bash
make api-create-sql-film-dim NAME=film_dim_full BATCH=2
```

Copy the returned `id` (pipeline UUID) → use it as `ID`.

Run it:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

Verify row counts:

```bash
make db-counts
```

---

## 2) Incremental mode (checkpoint + idempotency)

Create an incremental pipeline:

```bash
make api-create-sql-film-dim-inc NAME=film_dim_inc BATCH=2
```

Copy its `id` → `ID`.

Make sure `incremental_id_key` is set:

```bash
make db-set-inc-id-key ID=<ID> INC_ID_KEY=film_id
```

First run (should process data and save checkpoint):

```bash
make api-run ID=<ID>
make db-inc-state ID=<ID>
make db-last-run ID=<ID>
```

Second run without changes (expected: `rows_read=0`, `rows_written=0`):

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

Trigger a single-row change in source data:

```bash
make db-touch-filmwork-one
```

Run again (expected: a small incremental batch, often 1 row):

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

## 3) Tasks v1 (SQL reader + Python transform)

This shows how a pipeline can be defined as an execution plan (tasks), not only a single `source_query`.

1) Create a tasks-based FULL pipeline:

```bash
make api-create-tasks-film-dim-full NAME=film_dim_tasks_full
```

Copy `id` → `ID`.

Insert the task plan (SQL reader + PYTHON transform):

```bash
make db-tasks-clear ID=<ID>
make db-tasks-film-dim-full ID=<ID>
```
Run and verify:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
make db-counts
```
---

## 4) Pause / Resume (between batches)

Create a slow pipeline (adds `pg_sleep` per row):

```bash
make api-create-sql-film-dim-slow NAME=film_dim_slow BATCH=1 SLEEP=0.2
```

Copy `id` → `ID`.

Start and request pause after a short delay:

```bash
make api-run-and-pause ID=<ID> DELAY=1
make api-watch-status ID=<ID> N=20 DT=0.2
```

Expected: status becomes `PAUSED`.

Resume:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

---

## 5) Retry / fault tolerance (flip target table)

Create a pipeline:

```bash
make api-create-sql-film-dim NAME=film_dim_retry BATCH=1
```

Copy `id` → `ID`.

Run + simulate a temporary failure by renaming the target table during execution:

```bash
make test-retry-flip-film-dim ID=<ID>
```

Watch logs:

```bash
make logs-runner
```

Expected:

* warnings about failed attempts
* retry with backoff
* recovery after the table is restored

---

## 6) Elasticsearch sink demo

Create an Elasticsearch pipeline:

```bash
make api-create-es-film-dim NAME=film_dim_es BATCH=2
```

Copy `id` → `ID`.

Run it:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

Query Elasticsearch:

```bash
make es-demo
```

---

## Notes

* API runs are requested via `POST /pipelines/{id}/run`.
* The runner polls the DB and atomically claims `RUN_REQUESTED → RUNNING`.
* Incremental pipelines persist checkpoint in `etl.etl_state`.
* Writes are idempotent (safe retries).

---
## Related docs

- Detailed validation scenarios: `docs/VALIDATION_SCENARIOS.md`
- Architecture: `docs/ARCHITECTURE.md`
