
---

# Validation Scenarios — Fault-Tolerant ETL Platform

This document defines **deterministic validation scenarios** for the ETL platform.

Unlike `demo.md`, this file focuses on **invariants, edge cases, and failure semantics**, not on presentation.

---

## 0. Environment sanity

```bash
make build
make up
make alembic-up
make api-health
```

Runner logs (recommended):

```bash
make logs-runner
```

---

## 1. Full pipeline invariants

### Invariant: full pipeline is idempotent

**Goal:** running the same full pipeline multiple times must not corrupt data.

```bash
make db-reset-demo
make api-create-sql-film-dim NAME=full_idempotency_test BATCH=2
```

Copy returned `id` → `<ID>`

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

Run again:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

#### Expected

* `rows_read > 0` on both runs
* `rows_written > 0` on both runs
* no duplicates in `analytics.film_dim`
* final table state is identical

#### Violation means

Broken UPSERT or idempotency logic.

---

## 2. Incremental invariants

### Invariant: checkpoint persists

```bash
make api-create-sql-film-dim-inc NAME=inc_cursor_test BATCH=2
make db-set-inc-id-key ID=<ID> INC_ID_KEY=film_id
```

First run:

```bash
make api-run ID=<ID>
make db-inc-state ID=<ID>
make db-last-run ID=<ID>
```

Second run (no source changes):

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

#### Expected

* `rows_read = 0`
* `rows_written = 0`
* checkpoint unchanged

---

### Invariant: single-row change is detected

```bash
make db-touch-filmwork-one
make api-run ID=<ID>
make db-last-run ID=<ID>
```

#### Expected

* `rows_read = 1` (or small batch)
* `rows_written = 1`
* checkpoint advanced

#### Violation means

Broken cursor logic or ordering.

---

## 3. Pause / Resume invariants

### Invariant: pause only occurs between batches

```bash
make api-create-sql-film-dim-slow NAME=pause_test BATCH=1 SLEEP=0.2
```

```bash
make api-run-and-pause ID=<ID> DELAY=1
make api-watch-status ID=<ID> N=20 DT=0.2
```

#### Expected

* status becomes `PAUSED`
* no partial batch writes
* checkpoint is committed

Resume:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

#### Violation means

Unsafe pause semantics.

---

## 4. Retry / backoff invariants

### Invariant: transient failures are retried

```bash
make api-create-sql-film-dim NAME=retry_test BATCH=1
make test-retry-flip-film-dim ID=<ID>
make logs-runner
```

#### Expected

* warnings about failed attempts
* retries with backoff
* eventual success after table is restored

#### Violation means

Broken retry or error handling.

---

## 5. Elasticsearch sink invariants

### Invariant: ES writes are idempotent

```bash
make api-create-es-film-dim BATCH=2
make api-run ID=<ID>
make api-run ID=<ID>
make es-demo
```

#### Expected

* no duplicated documents
* stable document `_id`
* bulk upserts

#### Violation means

Broken ES writer semantics.

---

## 6. Atomic claim invariants

### Invariant: only one runner executes a pipeline

```bash
make api-run-parallel2 ID=<ID>
make api-runs-delta2 ID=<ID>
```

#### Expected

* at most 1 real execution
* no duplicate runs

#### Violation means

Broken atomic claim.

---

## 7. Tasks v1 invariants (if enabled)

### Invariant: SQL reader must be first

Insert invalid order manually → expect validation failure.

---

### Invariant: target override allowed only on last step

Violation → validation error.

---

### Invariant: incremental cursor is based on reader output

Transforms must not affect checkpoint.

---

## 8. Allowlist invariants

### Invariant: forbidden targets are rejected

Try:

* unknown Postgres table
* unknown ES index

#### Expected

* API validation error
* no execution

---

## 9. Crash recovery invariants

### Invariant: stuck RUNNING pipelines are recovered

Steps:

1. Start pipeline
2. Kill runner container
3. Restart runner

#### Expected

* pipeline not permanently stuck
* state recovered

---

## 10. Coverage summary

| Feature         | Covered |
| --------------- | ------- |
| Full pipelines  | ✅       |
| Incremental     | ✅       |
| Checkpointing   | ✅       |
| Pause / resume  | ✅       |
| Retry           | ✅       |
| Fault tolerance | ✅       |
| ES sink         | ✅       |
| Atomic claim    | ✅       |
| Tasks v1        | ✅       |
| Allowlist       | ✅       |
| Recovery        | ✅       |

---