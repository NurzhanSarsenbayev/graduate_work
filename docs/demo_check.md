
# 📄 docs/demo_checks.md

*Демо-проверки (Makefile-first)*

## 0) Старт и sanity-check

```bash
make up
make api-health
```

Опционально (на фоне, чтобы видеть раннер):

```bash
make logs-runner
```

---

## 1) SQL full → Postgres (analytics.film_dim)

1. Очистить демо-таблицы/состояние:

```bash
make db-reset-demo
make db-counts
```

2. Создать пайплайн:

```bash
make api-create-sql-film-dim NAME=film_dim_sql_full BATCH=2
```

Скопируй `id` из ответа → это `ID`.

3. Запуск:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

4. Проверка результата:

```bash
make db-counts
```

---

## 2) SQL incremental → Postgres (state + idempotency)

1. Создать incremental пайплайн:

```bash
make api-create-sql-film-dim-inc NAME=film_dim_sql BATCH=2
```

Скопируй `id` → `ID`.

2. (Важно) Поставить `incremental_id_key`, если в create не записался:

```bash
make db-set-inc-id-key ID=<ID> INC_ID_KEY=film_id
```

3. Первый запуск + проверка state:

```bash
make api-run ID=<ID>
make db-inc-state ID=<ID>
```

4. Второй запуск без изменений (ожидаем `read=0 written=0`):

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

5. Изменить одну строку source (чтобы было что инкрементально читать):

```bash
make db-touch-filmwork-one
make api-run ID=<ID>
make db-last-run ID=<ID>
```

---

## 3) Retry/backoff (тест “сломать витрину на лету”)

Создай SQL full пайплайн (или используй существующий) и возьми его `ID`.

```bash
make api-create-sql-film-dim NAME=film_dim_retry_full BATCH=1
```

`ID` из ответа.

Запуск + “сломать/вернуть” таблицу во время работы:

```bash
make test-retry-flip-film-dim ID=<ID>
make logs-runner
```

Ожидаем:

* в логах ретраи
* пайплайн в итоге успешный (или корректный fail если так настроено)

---

## 4) Tasks v1 — FULL (SQL reader + PYTHON transform → Postgres)

1. Создать pipeline tasks full:

```bash
make api-create-tasks-film-dim-full
```

Скопируй `id` → `ID`.

2. На всякий случай очистить tasks (если пересоздаёшь/повторяешь):

```bash
make db-tasks-clear ID=<ID>
```

3. Добавить tasks (2 шага: SQL + PYTHON):

```bash
make db-tasks-film-dim-full ID=<ID>
```

4. Запуск + проверка:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
make db-counts
```

Если хочешь прям “видимый эффект”, глянь titles в БД через psql вручную (у тебя это не завязано на make-таргет):

```bash
docker exec -it infra-etl_db-1 psql -U etl_user -d etl_demo -c "SELECT film_id,title FROM analytics.film_dim LIMIT 5;"
```

---

## 5) Tasks v1 — INCREMENTAL (state + idempotency)

1. Создать pipeline tasks incremental:

```bash
make api-create-tasks-film-dim-inc
```

Скопируй `id` → `ID`.

2. (Если нужно) проставить incremental_id_key (ты уже это ловил):

```bash
make db-set-inc-id-key ID=<ID> INC_ID_KEY=film_id
```

3. Очистить tasks и добавить нужные:

```bash
make db-tasks-clear ID=<ID>
make db-tasks-film-dim-inc ID=<ID>
```

4. Первый запуск + state:

```bash
make api-run ID=<ID>
make db-inc-state ID=<ID>
make db-last-run ID=<ID>
```

5. Второй запуск (ожидаем `read=0 written=0`):

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

6. Триггерим изменение в source и снова запускаем:

```bash
make db-touch-filmwork-one
make api-run ID=<ID>
make db-last-run ID=<ID>
```

---

## 6) Pause/Resume (между батчами) — через slow pipeline

### Вариант A: SQL full slow + “run and pause”

1. Создать медленный пайплайн:

```bash
make api-create-sql-film-dim-slow NAME=film_dim_slow BATCH=1 SLEEP=0.2
```

Скопируй `id` → `ID`.

2. Запуск + пауза:

```bash
make api-run-and-pause ID=<ID> DELAY=1
make api-watch-status ID=<ID> N=20 DT=0.2
```

Ожидаем:

* статус уйдёт в `PAUSED`

3. Resume:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

---

## 7) ES sink — full

1. Создать ES pipeline:

```bash
make api-create-es-film-dim BATCH=2
```

Скопируй `id` → `ID`.

2. Запуск:

```bash
make api-run ID=<ID>
make db-last-run ID=<ID>
```

3. Проверка в Elasticsearch:

```bash
curl -s "http://127.0.0.1:9200/film_dim/_search?size=3" | jq
```

---

## 8) Параллельный запуск (проверка атомарного claim)

Выбери любой pipeline `ID`:

```bash
make api-run-parallel2 ID=<ID>
make api-runs-delta2 ID=<ID>
```

Ожидаем:

* `delta` не “взрывается” мусорными runs
* (идеально) один реальный запуск, второй либо no-op/отклонён логикой
