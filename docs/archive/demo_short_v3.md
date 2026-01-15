Ниже — **готовый сценарий демо** (шаги + команды), заточенный под то, что ты хочешь показать: **пайплайны, статусы, runs, ES**. Я даю 2 варианта: **короткое демо (5–7 минут)** и **расширенное (10–12 минут)**. Команды — только из твоего Makefile + пару `curl` к ES.

---

# Вариант 1 — короткое демо 5–7 минут (рекомендую)

## 0) Старт и чистое состояние

```bash
make down-v
make up
make api-health
make db-counts
make api-list
```

Что говоришь:

* “Стартуем стек, проверяем health, показываем, что БД пустая по витринам/стейту/runs, пайплайнов нет.”

---

## 1) Создать 2 пайплайна: Postgres sink и ES sink

### 1.1 Film dim → Postgres витрина

```bash
make api-create-sql-film-dim NAME=film_dim_sql BATCH=100
```

### 1.2 Film dim → Elasticsearch индекс

```bash
make api-create-es-film-dim BATCH=100
```

Показать список:

```bash
make api-list
```

Скопируй ID двух пайплайнов (или сразу в уме: один sql, один es).

---

## 2) Показать статусы “IDLE → RUN_REQUESTED → RUNNING → SUCCESS”

### 2.1 Запуск SQL пайплайна

```bash
make api-run ID=<SQL_PIPE_ID>
make api-watch-status ID=<SQL_PIPE_ID> N=20 DT=0.2
make api-runs ID=<SQL_PIPE_ID>
make db-counts
```

Что говоришь:

* “Я дергаю /run — статус меняется, раннер подхватывает, создаётся run, витрина наполняется.”

---

## 3) Показать ES работает “по факту”

### 3.1 Запуск ES пайплайна

```bash
make api-run ID=<ES_PIPE_ID>
make api-watch-status ID=<ES_PIPE_ID> N=20 DT=0.2
make api-runs ID=<ES_PIPE_ID>
```

### 3.2 Проверка ES индекса (ключевой вау-момент)

```bash
curl -s http://127.0.0.1:9200/_cat/indices?v
curl -s http://127.0.0.1:9200/film_dim/_count | jq .
curl -s "http://127.0.0.1:9200/film_dim/_search?size=3" | jq '.hits.hits[]._source'
```

Что говоришь:

* “Индекс создался автоматически, документы залиты bulk-операцией, количество совпадает с written в run.”

---

## 4) Закрыть демо: логи раннера (коротко)

```bash
make logs-runner
```

Показать “SUCCESS read/written”, можно выйти Ctrl+C.

---

# Вариант 2 — расширенное демо 10–12 минут (если будут вопросы)

Добавляем **pause**, **retry**, **incremental state**.

---

## A) Демонстрация pause (нужен slow pipeline)

Создаём медленный пайплайн, чтобы успеть нажать pause:

```bash
make api-create-sql-film-dim-slow NAME=film_dim_sql_slow BATCH=2 SLEEP=0.2
make api-list
```

Запусти и почти сразу поставь pause:

```bash
make api-run-and-pause ID=<SLOW_PIPE_ID> DELAY=1
make api-watch-status ID=<SLOW_PIPE_ID> N=40 DT=0.2
make api-runs ID=<SLOW_PIPE_ID>
```

Что говоришь:

* “Показываю управляемость: можно запросить паузу, раннер обработает PAUSE_REQUESTED → PAUSED.”

> Если у тебя pause реализован как “поставить флаг и остановить после батча”, это идеально.

---

## B) Демонстрация retry (у тебя уже есть тест-хелпер)

```bash
make test-retry-flip-film-dim ID=<SQL_PIPE_ID>
make logs-runner
```

Что говоришь:

* “Я имитирую проблему на стороне витрины (переименование таблицы), раннер ловит ошибку, ретраит, после восстановления продолжает/завершает.”

Если хочешь более “чистый” вариант: после этого покажи `api-runs`.

---

## C) Демонстрация incremental state (если хочешь показать state table)

Создание incremental пайплайна:

```bash
make api-create-sql-film-dim-inc NAME=film_dim_sql BATCH=100
make api-list
```

Запуск:

```bash
make api-run ID=<INC_PIPE_ID>
make api-runs ID=<INC_PIPE_ID>
make db-inc-state ID=<INC_PIPE_ID>
```

Потом “изменим одну запись” и снова прогон:

```bash
make db-touch-filmwork-one
make api-run ID=<INC_PIPE_ID>
make api-runs ID=<INC_PIPE_ID>
make db-inc-state ID=<INC_PIPE_ID>
```

Что говоришь:

* “Инкрементальный пайплайн хранит курсор (last_processed_value/id), после изменения одной записи забирает только дельту.”

---

# Важные поправки к Makefile перед демо (очень советую)

## 1) В ES rating agg у тебя NAME по умолчанию `film_dim_sql` — это ловушка

Сделай вызов **всегда с NAME=...**, иначе будешь получать “already exists” или путаницу.

Пример:

```bash
make api-create-es-film-rating-agg NAME=film_rating_agg_es BATCH=100
```

## 2) Я бы сделал один “фиксированный набор имён” для демо

Чтобы не думать:

* `film_dim_sql`
* `film_dim_es`
* `film_dim_sql_slow`
* `film_dim_sql_inc`
* `film_rating_agg_es`

---

# Мой “скрипт демо” в одну шпаргалку (копируй)

**Подставляешь ID после `make api-list`.**

```bash
make down-v
make up
make api-health
make db-counts
make api-list

make api-create-sql-film-dim NAME=film_dim_sql
make api-create-es-film-dim BATCH=1
make api-create-sql-film-dim-slow NAME=film_dim_sql_slow BATCH=1 SLEEP=0.2
make api-create-sql-film-dim-inc-slow NAME=film_dim_sql BATCH=1 SLEEP=0.2
make api-list

make api-run ID=<SQL_PIPE_ID>
make api-watch-status ID=<SQL_PIPE_ID> N=20 DT=0.2
make api-runs ID=<SQL_PIPE_ID>
make db-counts

make api-run ID=<ES_PIPE_ID>
make api-watch-status ID=<ES_PIPE_ID> N=20 DT=0.2
make api-runs ID=<ES_PIPE_ID>

make test-retry-flip-film-dim ID=<FILM_DIM_SQL_ID>

make api-run-and-pause ID=<FILM_DIM_SQL_SLOW_ID> DELAY=1
make api-watch-status ID=<FILM_DIM_SQL_SLOW_ID> N=40 DT=0.2
make api-runs ID=<FILM_DIM_SQL_SLOW_ID>

make api-run ID=<FILM_DIM_INC_SLOW_ID>

curl -s http://127.0.0.1:9200/_cat/indices?v
curl -s http://127.0.0.1:9200/film_dim/_count | jq .
curl -s "http://127.0.0.1:9200/film_dim/_search?size=3" | jq '.hits.hits[]._source'
```

---

Если хочешь, я могу прямо сейчас помочь тебе сделать **ещё удобнее**: добавить в Makefile две команды:

* `make demo-setup` (поднимает, чистит, создаёт пайплайны)
* `make demo-es-check` (cat/ count/ search)

Но даже без этого, список выше завтра уже будет выглядеть “как прод”.
