
````markdown
# 📡 ETL API — контракт для сервиса управления пайплайнами

Версия: **v1 (MVP)**  
Назначение: описать фактическое поведение FastAPI-приложения на текущем этапе (неделя 2).

---

## 1. Общие принципы

- Базовый URL: `/api/v1`
- Формат данных: `application/json`
- Идентификаторы пайплайнов и запусков — UUID (строка).
- Все успешные ответы (кроме потенциальных `204 No Content`) возвращают JSON.
- Базовый формат ошибок:

```json
{
  "detail": "Человеко-понятное описание проблемы"
}
````

Примеры конкретных сообщений перечислены в разделе [Ошибки](#5-ошибки-и-коды-ответов).

---

## 2. Модели данных (API-уровень)

Здесь описаны **Pydantic-схемы**, используемые в публичном API.

### 2.1. `PipelineCreate` — создание пайплайна

Тело запроса `POST /api/v1/pipelines/`:

```json
{
  "name": "film_dim_full",
  "description": "Full reload of film_dim",
  "type": "SQL",
  "mode": "full",
  "enabled": true,
  "target_table": "analytics.film_dim",
  "batch_size": 100,
  "source_query": "SELECT id as film_id, title, rating FROM content.film_work"
}
```

Поля:

* `name` — уникальное имя пайплайна.
* `description` — опциональное описание.
* `type` — тип пайплайна, сейчас поддерживается только `"SQL"` (по умолчанию `"SQL"`).
* `mode` — режим, сейчас используется `"full"` (по умолчанию `"full"`).
* `enabled` — включён/выключен пайплайн (по умолчанию `true`).
* `target_table` — целевая таблица в схеме `analytics.*`.
  На текущем этапе допускаются значения из `ALLOWED_TARGET_TABLES`:

  * `analytics.film_dim`
  * `analytics.film_rating_agg`
* `batch_size` — размер батча (по умолчанию `1000`).
* `source_query` — SQL-запрос-источник.

> На уровне API поля `incremental_key`, `created_at`, `updated_at` пока **не возвращаются**.

---

### 2.2. `PipelineOut` — представление пайплайна в ответах

Ответы большинства эндпоинтов `/pipelines` используют эту форму:

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline (disabled for now)",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "PAUSED",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

Поля:

* `id` — UUID пайплайна.
* `name`, `description` — имя и описание.
* `type` — `"SQL"` / `"PYTHON"` (сейчас фактически используется `"SQL"`).
* `mode` — `"full"` / `"incremental"` (MVP: используется `"full"`).
* `enabled` — флаг включения.
* `status` — одно из:

  * `IDLE`
  * `RUNNING`
  * `PAUSED`
  * `FAILED`
* `target_table` — целевая таблица (`analytics.film_dim`, `analytics.film_rating_agg` и т.п.).
* `batch_size` — размер батча.

---

### 2.3. `PipelineUpdate` — частичное обновление

Тело запроса `PATCH /api/v1/pipelines/{pipeline_id}`:

```json
{
  "name": "film_dim_full_v2",
  "description": "Updated description",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "target_table": "analytics.film_dim",
  "batch_size": 500,
  "source_query": "SELECT id as film_id, title, rating FROM content.film_work WHERE rating IS NOT NULL"
}
```

Все поля **опциональны**. Отправляются только те, которые нужно поменять.

Ограничения бизнес-логики:

* если пайплайн в статусе `RUNNING`, любые попытки обновить конфигурацию приводят к ошибке `409 Conflict` (см. [Ошибки](#5-ошибки-и-коды-ответов)).

---

### 2.4. `PipelineRunOut` — запуск пайплайна

Ответ `GET /api/v1/pipelines/{pipeline_id}/runs`:

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

Поля:

* `id` — UUID запуска.
* `status` — `"RUNNING"`, `"SUCCESS"`, `"FAILED"`.
* `started_at` — время старта (UTC).
* `finished_at` — время завершения или `null`, если запуск ещё идёт.
* `rows_read` — количество строк, прочитанных из источника.
* `rows_written` — количество строк, записанных в целевую таблицу.
* `error_message` — текст ошибки при `FAILED` (может быть `null`).

> На текущем этапе `pipeline_id` внутрь `PipelineRunOut` не включён, так как всегда запрашивается история по конкретному пайплайну.

---

## 3. Эндпоинты по пайплайнам

Все эндпоинты находятся под префиксом:
`/api/v1/pipelines`

### 3.1. `GET /api/v1/pipelines/` — список пайплайнов

**Описание:**
Вернуть список всех пайплайнов.

**Пример ответа:**

```json
[
  {
    "id": "be239deb-055a-4c6f-9547-783e462041f8",
    "name": "film_dim_full",
    "description": "Full load film_dim pipeline (disabled for now)",
    "type": "SQL",
    "mode": "full",
    "enabled": false,
    "status": "PAUSED",
    "target_table": "analytics.film_dim",
    "batch_size": 500
  },
  {
    "id": "2f36a4ab-d010-47f4-8cfb-91d89dbc78ed",
    "name": "ratings_full",
    "description": "Full rebuild of analytics.film_rating_agg from ugc.ratings",
    "type": "SQL",
    "mode": "full",
    "enabled": true,
    "status": "IDLE",
    "target_table": "analytics.film_rating_agg",
    "batch_size": 100
  }
]
```

Коды ответов:

* `200 OK` — успешная выдача списка.

---

### 3.2. `POST /api/v1/pipelines/` — создать пайплайн

**Описание:**
Создаёт новый ETL-пайплайн.

**Тело запроса:** `PipelineCreate`.

**Пример успешного запроса:**

```json
{
  "name": "film_dim_full_v2",
  "description": "Full reload of film_dim (v2)",
  "type": "SQL",
  "mode": "full",
  "enabled": true,
  "batch_size": 100,
  "target_table": "analytics.film_dim",
  "source_query": "SELECT id as film_id, title, rating FROM content.film_work"
}
```

**Пример ответа (201):**

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

Возможные ошибки:

* `400 Bad Request`:

  * `target_table 'analytics.some_unknown_table' is not allowed`
  * `Pipeline with this name already exists`
* `422 Unprocessable Entity` — ошибки валидации входных данных (Pydantic).

---

### 3.3. `GET /api/v1/pipelines/{pipeline_id}` — получить пайплайн

**Описание:**
Вернуть информацию о конкретном пайплайне по `id`.

**Пример ответа (200):**

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline (disabled for now)",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "PAUSED",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

Ошибки:

* `404 Not Found` — `{"detail": "Pipeline not found"}`

---

### 3.4. `PATCH /api/v1/pipelines/{pipeline_id}` — частичное обновление

**Описание:**
Частично обновляет конфигурацию пайплайна.
Если в теле запроса нет ни одного поля (пустой `{}`), API просто возвращает текущую версию.

**Пример запроса:**

```json
{
  "batch_size": 500,
  "enabled": false
}
```

**Пример ответа (200):**

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline (disabled for now)",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "PAUSED",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

Ошибки:

* `404 Not Found` — пайплайн не найден.
* `409 Conflict` — `{"detail": "Cannot update pipeline while it is RUNNING"}`
  (domенное правило: нельзя менять конфиг активного пайплайна).
* `422 Unprocessable Entity` — некорректные типы/значения полей.

---

## 4. Управление статусом пайплайна (run / pause)

### 4.1. `POST /api/v1/pipelines/{pipeline_id}/run` — запуск

**Описание:**
Переводит пайплайн в статус `RUNNING`.
Если он уже в `RUNNING`, просто возвращается текущий объект без ошибки.

**Пример ответа (200):**

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline (disabled for now)",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "RUNNING",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

Ошибки:

* `404 Not Found` — `{"detail": "Pipeline not found"}`.

---

### 4.2. `POST /api/v1/pipelines/{pipeline_id}/pause` — пауза

**Описание:**
Переводит пайплайн в статус `PAUSED`.
Если он уже в `PAUSED`, возвращается объект как есть.

**Пример ответа (200):**

```json
{
  "id": "be239deb-055a-4c6f-9547-783e462041f8",
  "name": "film_dim_full",
  "description": "Full load film_dim pipeline (disabled for now)",
  "type": "SQL",
  "mode": "full",
  "enabled": false,
  "status": "PAUSED",
  "target_table": "analytics.film_dim",
  "batch_size": 500
}
```

Ошибки:

* `404 Not Found` — `{"detail": "Pipeline not found"}`.

---

## 5. История запусков пайплайна

### 5.1. `GET /api/v1/pipelines/{pipeline_id}/runs` — список запусков

**Описание:**
Возвращает историю запусков конкретного пайплайна.
Поддерживает параметр `limit` (по умолчанию `50`, от `1` до `500`).

**Пример запроса:**

```http
GET /api/v1/pipelines/be239deb-055a-4c6f-9547-783e462041f8/runs?limit=50
```

**Пример ответа (200):**

```json
[
  {
    "id": "8db9cb6a-7507-4b57-bda4-30e925605ffa",
    "status": "SUCCESS",
    "started_at": "2025-12-10T08:01:06.674452Z",
    "finished_at": "2025-12-10T08:01:06.699992Z",
    "rows_read": 10,
    "rows_written": 10,
    "error_message": null
  }
]
```

Ошибки:

* `404 Not Found` — если пайплайн не существует (`{"detail": "Pipeline not found"}`).

---

## 6. Ошибки и коды ответов

Сводка основных ошибок для `/pipelines`:

* `400 Bad Request`

  * `target_table '...' is not allowed`
  * `Pipeline with this name already exists`
* `404 Not Found`

  * `Pipeline not found`
* `409 Conflict`

  * `Cannot update pipeline while it is RUNNING`
* `422 Unprocessable Entity`

  * Ошибки валидации входных данных (стандартный формат FastAPI/Pydantic).

---

## 7. Что появится позже (TBD)

Это то, что заложено в архитектуру, но **пока не реализовано в API**:

* Эндпоинты для:

  * состояния пайплайна (`/state`, работа с `etl_state`);
  * reconciliation / сверки source/target;
  * расширенных фильтров и пагинации в `GET /pipelines`.
* Отдельный эндпоинт `GET /api/v1/health` (healthcheck сервиса).
* Поддержка Python-пайплайнов (`type = "PYTHON"`) и описания задач (`etl_pipeline_tasks`).

Факт наличия/отсутствия этих эндпоинтов нужно сверять по актуальному коду.

---
