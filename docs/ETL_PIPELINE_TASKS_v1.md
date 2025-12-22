
# 📄 `tasks_v1.md` — Pipeline Tasks v1

## Зачем нужны Tasks

`Tasks v1` — это расширение модели ETL-пайплайна, позволяющее описывать **цепочку шагов внутри одного пайплайна**, а не один “монолитный” `source_query`.

Основные цели:

* отделить **чтение данных** (SQL) от **трансформаций** (Python),
* переиспользовать существующую инфраструктуру пайплайнов (status, runs, state),
* подготовить архитектуру к будущему расширению (несколько reader’ов, branching и т.п.).

`Tasks v1` — это **осознанно ограниченный MVP**, а не финальный DSL.

---

## Общая идея

Pipeline с tasks выглядит так:

```
[ SQL reader ] → [ Python transform ] → [ Python transform ] → writer
```

* **Reader** — всегда один, всегда SQL.
* **Transform’ы** — 0 или больше Python-функций.
* **Writer** — определяется `target_table` (Postgres или Elasticsearch).

---

## Хранение в БД

### Таблица `etl.etl_pipeline_tasks`

```sql
CREATE TABLE etl.etl_pipeline_tasks (
    id           uuid PRIMARY KEY,
    pipeline_id  uuid NOT NULL REFERENCES etl.etl_pipelines(id),
    order_index  int  NOT NULL,
    task_type    text NOT NULL,   -- SQL | PYTHON
    body         text NOT NULL,   -- SQL query или python dotted path
    target_table text NULL        -- override target (только для последнего task)
);
```

### Связь с пайплайном

* `etl_pipelines` — описывает **пайплайн целиком**
* `etl_pipeline_tasks` — описывает **план выполнения (tasks)**

Если у пайплайна **есть tasks**, то:

* `source_query` в `etl_pipelines` **игнорируется**
* выполнение идёт через `tasks_*` runners

---

## Snapshot модель

```python
@dataclass(frozen=True, slots=True)
class TaskSnapshot:
    id: str
    order_index: int
    task_type: str        # SQL | PYTHON
    body: str             # query / dotted path
    target_table: str | None

@dataclass(frozen=True, slots=True)
class PipelineSnapshot:
    id: str
    name: str
    type: str
    mode: str             # full | incremental
    batch_size: int
    source_query: str | None
    python_module: str | None
    target_table: str
    incremental_key: str | None
    incremental_id_key: str | None
    description: str | None
    tasks: tuple[TaskSnapshot, ...]
```

---

## Контракт Tasks v1 (строгие правила)

Валидация выполняется в `validate_tasks_v1()`.

### 1. Порядок

* `order_index` должен быть **уникальным**
* tasks сортируются по `order_index`
* “дырки” допустимы (1, 10, 20), порядок важнее непрерывности

---

### 2. Типы шагов

* **Первый task** — строго `task_type = "SQL"`
* **Все остальные** — строго `task_type = "PYTHON"`

❌ Запрещено:

* Python первым
* SQL после первого шага
* любые другие типы

---

### 3. `body`

* не может быть пустым
* для `SQL` — SQL-запрос
* для `PYTHON` — dotted path до модуля с функцией `transform(rows)`

Пример:

```python
src.pipelines.python_tasks.normalize_title
```

---

### 4. Target override (упрощение v1)

* `target_table` **можно указывать только у последнего task**
* все промежуточные шаги **не имеют права** менять target

Финальный target определяется как:

```python
final_target = last_task.target_table or pipeline.target_table
```

---

### 5. Allowlist target’ов

Финальный target **обязан пройти allowlist**:

```python
def is_allowed_target(target: str) -> bool:
    if target in ALLOWED_TARGET_TABLES:
        return True
    if target.startswith("es:"):
        return target[3:] in ALLOWED_ES_INDEXES
    return False
```

❌ Любой неизвестный target — ошибка валидации.

---

## Execution flow

### Выбор стратегии

```python
if pipeline.tasks:
    snap = validate_tasks_v1(pipeline)
    run_tasks_full / run_tasks_incremental
else:
    run_sql_full / run_sql_incremental
```

---

## Tasks Full

Алгоритм:

1. SQL reader → `LIMIT / OFFSET`
2. Применить Python transforms **по порядку**
3. Записать batch через writer
4. Commit
5. Проверить pause
6. Повторить

---

## Tasks Incremental

Отличия:

* используется `incremental_key` + `incremental_id_key`
* reader SQL оборачивается в:

  ```sql
  SELECT * FROM (reader_sql) src
  WHERE (inc_key > last_ts)
     OR (inc_key = last_ts AND id_key > last_id)
  ORDER BY inc_key, id_key
  LIMIT :batch
  ```
* checkpoint берётся **по reader rows**, а не по transformed

Гарантии:

* второй запуск → `read = 0`
* после `touch` одной строки → `read = 1`

---

## Pause / Resume

* `PAUSE_REQUESTED` проверяется **после batch**
* состояние сохраняется через `etl_state`
* повторный `/run` продолжает с последнего checkpoint

---

## Ограничения v1 (осознанные)

❌ Не поддерживается:

* несколько SQL reader’ов
* branching / DAG
* conditionals
* параллельные task’и
* fan-out / fan-in

Это **не баги**, а границы MVP.

---

## Что дальше (v2 идеи)

* несколько reader’ов
* SQL → SQL transforms
* task-level retry/backoff
* branching
* визуальный task graph

---

## TL;DR

Tasks v1:

* ✅ один SQL reader
* ✅ python transforms
* ✅ full + incremental
* ✅ pause / resume
* ✅ Postgres + Elasticsearch targets
* ❌ без DAG и магии

---

