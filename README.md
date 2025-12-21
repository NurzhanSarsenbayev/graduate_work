
# ETL Platform — Postgres & Elasticsearch

ETL-платформа для построения аналитических витрин и поисковых индексов
в онлайн-кинотеатре.

Проект реализует **control-plane (ETL API)** и **data-plane (ETL Runner)**,
позволяя управлять пайплайнами через REST API и выполнять их асинхронно
в отдельном воркере.

---

## 🚀 Возможности (MVP)

- SQL-пайплайны (full / incremental)
- Батчевая обработка данных
- Idempotent UPSERT
- Pause / Resume
- Retry с backoff
- Восстановление после сбоев
- Target’ы:
  - PostgreSQL (`analytics.*`)
  - Elasticsearch (`es:<index>`)
- Управление через REST API
- Docker-first

---

## 🧱 Архитектура

```

Client
|
v
ETL API (FastAPI) ──► Postgres (etl schema)
▲
|
ETL Runner (worker)
|
+----------------+----------------+
|                                 |
PostgreSQL (analytics)          Elasticsearch

````

- **ETL API** — управление пайплайнами, статусы, валидация
- **ETL Runner** — выполнение ETL, state, retry, recovery
- **Postgres** — source + analytics + etl metadata
- **Elasticsearch** — поисковые/feature-витрины

Подробно см. `ARCHITECTURE.md`.

---

## 🐳 Запуск проекта

### 1. Подготовка

```bash
cp .env.example .env
````

(по умолчанию всё уже настроено для docker-compose)

### 2. Запуск

```bash
make up
```

Проверки:

```bash
curl http://localhost:8000/health
curl http://localhost:9200
```

---

## 📦 Создание пайплайнов

### 1. Postgres → Postgres (витрина)

```bash
make api-create-sql-film-rating-agg \
  NAME=film_rating_agg_pg \
  BATCH=200
```

### 2. Postgres → Elasticsearch

```bash
make api-create-sql-film-rating-agg \
  NAME=film_rating_agg_es \
  BATCH=200 \
  TARGET=es:film_rating_agg
```

Пример SQL:

```sql
SELECT
  r.film_id AS film_id,
  AVG(r.rating)::float8 AS avg_rating,
  COUNT(*)::int AS rating_count
FROM ugc.ratings r
GROUP BY r.film_id
```

---

## ▶️ Запуск пайплайна

```bash
make api-run ID=<pipeline_id>
```

Runner автоматически подхватит `RUN_REQUESTED`
и выполнит пайплайн.

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

Разрешены только whitelisted target’ы:

```python
ALLOWED_TARGET_TABLES = {
    "analytics.film_dim",
    "analytics.film_rating_agg",
}

ALLOWED_ES_INDEXES = {
    "film_dim",
    "film_rating_agg",
}
```

Попытка писать в другой индекс или таблицу будет отклонена
на уровне API и Runner.

---

## 🧠 Состояния пайплайна

* `IDLE`
* `RUN_REQUESTED`
* `RUNNING`
* `PAUSED`
* `FAILED`

Retry:

* 3 попытки
* 1s → 2s → 4s

---

## 📂 Структура проекта

```
src/
  app/        # ETL API (FastAPI)
  runner/     # ETL Runner (worker)
infra/
  docker-compose.yml
```

Подробно — см. `ARCHITECTURE.md`.

---

## 🔭 Планы развития

* Python-трансформации
* Multi-task pipelines
* Schedules (cron / Airflow)
* Metrics (Prometheus)
* Dead-letter queues
* S3 / Kafka источники

---

## 🧑‍💻 Автор

Nurzhan Sarsenbayev
Diploma Project — Python Backend / Data Engineering

