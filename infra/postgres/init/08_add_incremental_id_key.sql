-- 08_add_incremental_id_key.sql
SET search_path = etl, public;

ALTER TABLE etl.etl_pipelines
ADD COLUMN IF NOT EXISTS incremental_id_key text;