

# ETL Platform — Postgres & Elasticsearch

ETL-платформа для построения аналитических витрин и поисковых индексов
в онлайн-кинотеатре.

Проект реализует разделение на:

* **Control-plane** — ETL API (FastAPI)
* **Data-plane** — ETL Runner (Python worker)

Это позволяет управлять пайплайнами через REST API
и выполнять ETL асинхронно в отдельном процессе.

---

## 🚀 Возможности (MVP)

* SQL-пайплайны (`full` / `incremental`)
* **Pipeline Tasks (v1)**:

  * SQL reader + Python transforms
* Батчевая обработка данных
* Idempotent UPSERT
* Pause / Resume (между батчами)
* Retry с backoff (1 / 2 / 4 сек)
* Recovery после сбоев
* Sink’и:

  * PostgreSQL (`analytics.*`)
  * Elasticsearch (`es:<index>`)
* Управление через REST API
* Docker-first

---

## 🧩 Pipeline Tasks (v1)

Pipeline может быть описан **двумя способами**:

1. **Legacy mode** — через `source_query`
2. **Tasks mode (v1)** — через линейный task plan

Если у пайплайна определены tasks, они имеют приоритет над `source_query`.

### Ограничения v1 (осознанный MVP)

* задачи выполняются **строго последовательно**
* **первый шаг — SQL reader**
* последующие шаги — **Python transforms**
* DAG, branching и параллельность **не поддерживаются**
* pipeline остаётся **одним execution unit**

Пример:

```
[ SQL reader ] → [ Python transform ] → sink
```

---

## 🧱 Архитектура (кратко)

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

* **ETL API** — управление пайплайнами и статусами
* **ETL Runner** — выполнение ETL, state, retry, recovery
* **Postgres** — source + analytics + ETL metadata
* **Elasticsearch** — поисковые / feature-витрины

Подробно см. `ARCHITECTURE.md`.

---

## 🐳 Запуск проекта

### 1. Подготовка

```bash
cp .env.example .env
```

(значения по умолчанию подходят для `docker-compose`)

### 2. Запуск

```bash
make up
```

Проверка сервисов:

```bash
curl http://localhost:8000/api/v1/health
curl http://localhost:9200
```

---

## 📦 Создание пайплайнов

### 1. SQL → Postgres (витрина)

```bash
make api-create-sql-film-rating-agg \
  NAME=film_rating_agg_pg \
  BATCH=200
```

### 2. SQL → Elasticsearch

```bash
make api-create-es-film-rating-agg \
  NAME=film_rating_agg_es \
  BATCH=200
```

---

## ▶️ Запуск пайплайна

```bash
make api-run ID=<pipeline_id>
```

Runner автоматически подхватит `RUN_REQUESTED`
и выполнит пайплайн.

---

## ⏸ Pause / Resume

```bash
make api-pause ID=<pipeline_id>
make api-run   ID=<pipeline_id>
```

⚠️ Пауза применяется **между батчами** — текущий batch
всегда корректно завершается.

---

## 🔎 Проверка результата

### PostgreSQL

```sql
SELECT * FROM analytics.film_rating_agg LIMIT 5;
```

### Elasticsearch

```bash
curl "http://localhost:9200/film_rating_agg/_search?size=5" | jq
```

---

## 🔐 Ограничения безопасности (MVP)

Разрешены только whitelisted target’ы.

Postgres:

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

Попытка писать в другой target будет отклонена
на уровне API и Runner.

---

## 🧠 Состояния пайплайна

* `IDLE`
* `RUN_REQUESTED`
* `RUNNING`
* `PAUSE_REQUESTED`
* `PAUSED`
* `FAILED`

Retry:

* 3 попытки
* backoff: 1s → 2s → 4s

---

## 📂 Структура проекта

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

## 🔍 Проверочные сценарии

Подробные пошаговые проверки (full / incremental / tasks / pause / ES)
вынесены в отдельный файл:

👉 **`docs/demo_checks.md`**

---

## 🔭 Планы развития

* DAG-based task plans (beyond linear v1)
* Параллельное выполнение задач
* Schedules (cron / Airflow)
* Metrics (Prometheus)
* DLQ
* Новые sink’и (S3 / ClickHouse)

---

## 🧑‍💻 Автор

**Nurzhan Sarsenbayev**
Diploma Project — Python Backend / Data Engineering

---
