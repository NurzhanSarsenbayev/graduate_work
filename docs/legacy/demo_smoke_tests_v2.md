Ок, давай сделаем себе нормальный чеклист, чтобы каждый рефактор не превращался в угадайку.
Вот **полный набор проверок для `/api/v1/pipelines`**, который можно тупо копипастить.

---

## 0. Базовая переменная

После успешного создания пайплайна вытащишь `id` и подставишь:

```bash
PIPELINE_ID=<сюда вставь UUID существующего пайплайна>
echo $PIPELINE_ID
```

---

## 1. Листинг пайплайнов

```bash
curl -v http://127.0.0.1:8000/api/v1/pipelines/
```

Ожидаем: `200 OK`, список пайплайнов.

---

## 2. Создание пайплайна (OK-кейс)

```bash
curl -v http://127.0.0.1:8000/api/v1/pipelines/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "film_dim_full_v2",
    "description": "Full reload of film_dim v2",
    "type": "SQL",
    "mode": "full",
    "enabled": true,
    "batch_size": 100,
    "target_table": "analytics.film_dim",
    "source_query": "SELECT id as film_id, title, rating FROM content.film_work"
  }'
```

Ожидаем: `201 Created`, в ответе есть `id` и `name`.

👉 После этого обнови `PIPELINE_ID` на этот новый id.

---

## 3. Создание с неправильным `target_table` → 400

```bash
curl -v http://127.0.0.1:8000/api/v1/pipelines/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "invalid_target",
    "description": "Should fail",
    "type": "SQL",
    "mode": "full",
    "enabled": true,
    "batch_size": 100,
    "target_table": "analytics.some_unknown_table",
    "source_query": "SELECT 1"
  }'
```

Ожидаем:
`400 Bad Request` с текстом типа:

```json
{"detail":"target_table 'analytics.some_unknown_table' is not allowed"}
```

---

## 4. Создание с дублирующим именем → 400

```bash
curl -v http://127.0.0.1:8000/api/v1/pipelines/ \
  -H "Content-Type: application/json" \
  -d '{
    "name": "film_dim_full_v2",
    "description": "Duplicate name",
    "type": "SQL",
    "mode": "full",
    "enabled": true,
    "batch_size": 100,
    "target_table": "analytics.film_dim",
    "source_query": "SELECT 1"
  }'
```

Ожидаем:
`400 Bad Request`:

```json
{"detail":"Pipeline with this name already exists"}
```

---

## 5. GET по существующему и несуществующему

```bash
# существующий
curl -v "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}"

# несуществующий
curl -v "http://127.0.0.1:8000/api/v1/pipelines/00000000-0000-0000-0000-000000000000"
```

Ожидаем:

* первый — `200 OK`;
* второй — `404 {"detail":"Pipeline not found"}`.

---

## 6. Запуск / пауза пайплайна

```bash
# run
curl -v -X POST \
  "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}/run"

# pause
curl -v -X POST \
  "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}/pause"

# run несуществующего
curl -v -X POST \
  "http://127.0.0.1:8000/api/v1/pipelines/00000000-0000-0000-0000-000000000000/run"
```

Ожидаем:

* `run` → `200` и `status: "RUNNING"` (если до этого был не RUNNING);
* `pause` → `200` и `status: "PAUSED"`;
* для несуществующего → `404 "Pipeline not found"`.

---

## 7. PATCH (обновление)

```bash
# нормальное частичное обновление
curl -v -X PATCH \
  "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}" \
  -H "Content-Type: application/json" \
  -d '{
    "batch_size": 500,
    "enabled": false
  }'

# пустой PATCH (ничего не меняем)
curl -v -X PATCH \
  "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}" \
  -H "Content-Type: application/json" \
  -d '{}'

# PATCH по несуществующему
curl -v -X PATCH \
  "http://127.0.0.1:8000/api/v1/pipelines/00000000-0000-0000-0000-000000000000" \
  -H "Content-Type: application/json" \
  -d '{"enabled": false}'
```

Ожидаем:

* первый → `200`, `batch_size: 500`, `enabled: false`;
* второй → `200`, те же данные, просто без изменений;
* третий → `404 "Pipeline not found"`.

(Чуть позже, когда сделаем полноценную проверку RUNNING → 409, сюда добавим сценарий с `status=RUNNING`.)

---

## 8. История запусков `/runs`

```bash
# по существующему
curl -v \
  "http://127.0.0.1:8000/api/v1/pipelines/${PIPELINE_ID}/runs?limit=50"

# по несуществующему
curl -v \
  "http://127.0.0.1:8000/api/v1/pipelines/00000000-0000-0000-0000-000000000000/runs"
```

Ожидаем:

* первый → `200 OK`, JSON-массив (может быть пустой, а может с одним/несколькими `runs`);
* второй → `404 "Pipeline not found"`.

---

Хочешь — можешь этот блок себе в `docs/demo_script.md` или `docs/demo_short.md` вставить как раздел **“Smoke-тест API pipelines”**.

Дальше давай так:

* если по любому из этих запросов что-то поедет (не тот статус, не тот detail) — кидаешь сюда конкретный `curl -v` + ответ;
* отдельно можем разобрать модели, как ты хотел, просто пришли текущие `EtlPipeline` и `EtlRun`.
