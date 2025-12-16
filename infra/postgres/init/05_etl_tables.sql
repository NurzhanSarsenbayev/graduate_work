CREATE SCHEMA IF NOT EXISTS etl;
SET search_path TO etl, public;

-- Основная таблица пайплайнов
CREATE TABLE IF NOT EXISTS etl_pipelines (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name            TEXT NOT NULL UNIQUE,
    description     TEXT,

    -- Тип пайплайна: SQL или PYTHON
    type            TEXT NOT NULL CHECK (type IN ('SQL', 'PYTHON')),

    -- Для SQL-пайплайнов: базовый запрос-источник
    -- Для PYTHON может быть NULL (логика живёт в python_task)
    source_query    TEXT,

    -- Для PYTHON-пайплайнов: dotted path до модуля/функции трансформации
    python_module   TEXT,

    target_table    TEXT NOT NULL,

    -- Режим работы: полный или инкрементальный
    mode            TEXT NOT NULL CHECK (mode IN ('full', 'incremental')),

    -- Ключ для инкремента (дата/ID), опционально
    incremental_key TEXT,

    batch_size      INTEGER NOT NULL DEFAULT 1000,
    enabled         BOOLEAN NOT NULL DEFAULT TRUE,

    -- Логический статус пайплайна
    status          TEXT NOT NULL DEFAULT 'IDLE'
                    CHECK (status IN ('IDLE', 'RUN_REQUESTED', 'RUNNING', 'PAUSE_REQUESTED', 'PAUSED', 'FAILED')),

    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Шаги (tasks) внутри пайплайна — архитектурно, для многошаговых ETL
CREATE TABLE IF NOT EXISTS etl_pipeline_tasks (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id  UUID NOT NULL REFERENCES etl_pipelines(id) ON DELETE CASCADE,
    order_index  INTEGER NOT NULL,    -- порядок выполнения

    task_type    TEXT NOT NULL CHECK (task_type IN ('SQL', 'PYTHON')),

    -- Для SQL: текст SQL; для PYTHON: имя зарегистрированной задачи
    body         TEXT NOT NULL,

    source_table TEXT,
    target_table TEXT,

    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    UNIQUE (pipeline_id, order_index)
);

-- Состояние пайплайна (checkpoint)
CREATE TABLE IF NOT EXISTS etl_state (
    pipeline_id          UUID PRIMARY KEY REFERENCES etl_pipelines(id) ON DELETE CASCADE,

    -- Можно использовать либо для ID, либо для даты/времени
    last_processed_id    TEXT,
    last_processed_value TEXT,

    updated_at           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- История запусков
CREATE TABLE IF NOT EXISTS etl_runs (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    pipeline_id   UUID NOT NULL REFERENCES etl_pipelines(id) ON DELETE CASCADE,

    started_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at   TIMESTAMPTZ,

    rows_read     INTEGER,
    rows_written  INTEGER,

    status        TEXT NOT NULL DEFAULT 'RUNNING'
                  CHECK (status IN ('RUNNING', 'SUCCESS', 'FAILED')),

    error_message TEXT
);

CREATE INDEX IF NOT EXISTS ix_etl_runs_pipeline_id_started_at
    ON etl_runs (pipeline_id, started_at DESC);
