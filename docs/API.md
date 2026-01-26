
# ETL API Reference

This document describes the public REST API of the **Fault-Tolerant ETL Platform**.
The API acts as a **control-plane**: it manages pipeline configuration and lifecycle, but never executes pipelines directly.

---

## Overview

- Base URL: `/api/v1`
- Content type: `application/json`
- Pipeline and run identifiers: UUID (string)
- All successful responses return JSON (except `204 No Content`)
- Error format:

```json
{
  "detail": "Human-readable error description"
}
````

---

## Data Models

This section describes the **public API schemas** (Pydantic-based).

---

### PipelineCreate

Request body for `POST /pipelines`.

```json
{
  "name": "film_dim_full",
  "description": "Full reload of film_dim",
  "type": "SQL",
  "mode": "full",
  "enabled": true,
  "target_table": "analytics.film_dim",
  "batch_size": 100,
  "source_query": "SELECT id AS film_id, title, rating FROM content.film_work"
}
```

#### Fields

* `name` — unique pipeline name
* `description` — optional description
* `type` — pipeline type (currently only `"SQL"` is supported)
* `mode` — execution mode (`"full"` or `"incremental"`)
* `enabled` — whether the pipeline is active
* `target_table` — sink target
* `batch_size` — batch size (default: `1000`)
* `source_query` — SQL source query

#### Target Restrictions

Only whitelisted targets are allowed.

PostgreSQL:

* `analytics.film_dim`
* `analytics.film_rating_agg`

Elasticsearch targets use the `es:` prefix (e.g., `es:film_dim`).

---

### PipelineOut

Returned by most `/pipelines` endpoints.

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "PAUSED",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

#### Fields

* `id` — pipeline UUID
* `name`, `description`
* `type` — `"SQL"` / `"PYTHON"` (future)
* `mode` — `"full"` / `"incremental"`
* `enabled`
* `status` — see [Pipeline States](#pipeline-states)
* `target_table`
* `batch_size`

---

### PipelineUpdate

Request body for `PATCH /pipelines/{pipeline_id}`.

All fields are optional.

```json
{
  "batch_size": 500,
  "enabled": false
}
```

#### Business Rules

* Pipelines in `RUNNING` state **cannot be modified**
* Violations result in `409 Conflict`

---

### PipelineRunOut

Returned by `/pipelines/{pipeline_id}/runs`.

```json
{
  "id": "8db9cb6a-7507-4b57-bda4-30e925605ffa",
  "status": "SUCCESS",
  "started_at": "2025-12-10T08:01:06.674452Z",
  "finished_at": "2025-12-10T08:01:06.699992Z",
  "rows_read": 10,
  "rows_written": 10,
  "error_message": null
}
```

#### Fields

* `id` — run UUID
* `status` — `"RUNNING"`, `"SUCCESS"`, `"FAILED"`
* `started_at` — UTC timestamp
* `finished_at` — UTC timestamp or `null`
* `rows_read`
* `rows_written`
* `error_message` — populated if `FAILED`

---

## Pipelines Endpoints

All endpoints are prefixed with:

```
/api/v1/pipelines
```

---

### GET `/pipelines`

Returns a list of all pipelines.

#### Response

```json
[
  {
    "id": "be239deb-055a-4c6f-9547-783e462041f8",
    "name": "film_dim_full",
    "description": "Full load film_dim pipeline",
    "type": "SQL",
    "mode": "full",
    "enabled": false,
    "status": "PAUSED",
    "target_table": "analytics.film_dim",
    "batch_size": 500
  }
]
```

#### Status Codes

* `200 OK`

---

### POST `/pipelines`

Creates a new pipeline.

#### Request Body

`PipelineCreate`

#### Response (201)

```json
{
  "id": "dd3fcb2b-8600-440d-9468-e5d26f35afa1",
  "name": "film_dim_full_v2",
  "description": "Full reload of film_dim (v2)",
  "type": "SQL",
  "mode": "full",
  "enabled": true,
  "status": "IDLE",
  "target_table": "analytics.film_dim",
  "batch_size": 100
}
```

#### Errors

* `400 Bad Request`

  * target is not allowed
  * pipeline name already exists
* `422 Unprocessable Entity` — validation errors

---

### GET `/pipelines/{pipeline_id}`

Returns a single pipeline.

#### Errors

* `404 Not Found`

---

### PATCH `/pipelines/{pipeline_id}`

Partially updates a pipeline configuration.

#### Business Rules

* Pipelines in `RUNNING` state cannot be updated

#### Errors

* `404 Not Found`
* `409 Conflict` — cannot update a running pipeline
* `422 Unprocessable Entity`

---

## Pipeline Lifecycle

### POST `/pipelines/{pipeline_id}/run`

Requests pipeline execution.

If the pipeline is already running, the current state is returned.

#### Errors

* `404 Not Found`

---

### POST `/pipelines/{pipeline_id}/pause`

Requests pipeline pause.

Pause is applied between batches.

#### Errors

* `404 Not Found`

---

## Pipeline Runs

### GET `/pipelines/{pipeline_id}/runs`

Returns pipeline run history.

#### Query Parameters

* `limit` (default: 50, min: 1, max: 500)

#### Errors

* `404 Not Found`

---

## Pipeline States

Pipelines are managed using an explicit state machine.

Possible states:

* `IDLE`
* `RUN_REQUESTED`
* `RUNNING`
* `PAUSE_REQUESTED`
* `PAUSED`
* `FAILED`

---

## Error Handling

Common error responses:

### 400 Bad Request

* Target is not allowed
* Duplicate pipeline name

### 404 Not Found

* Pipeline not found

### 409 Conflict

* Cannot update a running pipeline

### 422 Unprocessable Entity

* Schema validation errors

---

## Execution Semantics

The API does not execute pipelines.

Instead, it:

1. Persists configuration
2. Requests state transitions
3. Exposes pipeline status

Execution is performed asynchronously by the **ETL Runner**.

---

## Future Extensions

The following features are planned but not yet exposed:

* Pipeline state introspection (`/state`)
* Reconciliation endpoints
* Pagination and filtering for `/pipelines`
* Dedicated health endpoint (`/health`)
* Python-based pipelines
* Tasks-based pipeline definitions

---

## Summary

This API is intentionally minimal.

Its purpose is to:

* Control pipeline lifecycle
* Validate configuration
* Expose execution state

All execution logic is delegated to the data-plane.
