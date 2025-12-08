SET search_path TO etl, public;

CREATE TABLE IF NOT EXISTS etl_pipelines (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    source_query TEXT NOT NULL,
    target_table TEXT NOT NULL,
    mode TEXT NOT NULL,                -- 'full' / 'incremental'
    batch_size INTEGER DEFAULT 1000,
    enabled BOOLEAN DEFAULT TRUE,
    status TEXT DEFAULT 'IDLE',        -- IDLE / RUNNING / PAUSED / FAILED
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etl_state (
    pipeline_id UUID PRIMARY KEY REFERENCES etl_pipelines(id) ON DELETE CASCADE,
    last_processed_id TEXT,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS etl_runs (
    id UUID PRIMARY KEY,
    pipeline_id UUID REFERENCES etl_pipelines(id) ON DELETE CASCADE,
    started_at TIMESTAMP WITHOUT TIME ZONE,
    finished_at TIMESTAMP WITHOUT TIME ZONE,
    rows_read INTEGER DEFAULT 0,
    rows_written INTEGER DEFAULT 0,
    status TEXT                        -- SUCCESS / FAILED
);
