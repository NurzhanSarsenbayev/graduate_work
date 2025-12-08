-- Заполняем витрину analytics.film_dim из content.film_work
INSERT INTO analytics.film_dim (film_id, title, rating, updated_at)
SELECT
    fw.id        AS film_id,
    fw.title     AS title,
    fw.rating    AS rating,
    NOW()        AS updated_at
FROM content.film_work fw
ON CONFLICT (film_id) DO UPDATE
SET
    title      = EXCLUDED.title,
    rating     = EXCLUDED.rating,
    updated_at = NOW();


-- Заполняем витрину analytics.film_rating_agg из ugc.ratings
INSERT INTO analytics.film_rating_agg (film_id, avg_rating, votes_count, updated_at)
SELECT
    r.film_id,
    AVG(r.rating)::NUMERIC(3, 2) AS avg_rating,
    COUNT(*)::INT                AS votes_count,
    NOW()                        AS updated_at
FROM ugc.ratings r
GROUP BY r.film_id
ON CONFLICT (film_id) DO UPDATE
SET
    avg_rating  = EXCLUDED.avg_rating,
    votes_count = EXCLUDED.votes_count,
    updated_at  = NOW();


-- Добавляем два пайплайна в etl.etl_pipelines
INSERT INTO etl.etl_pipelines (
    id,
    name,
    source_query,
    target_table,
    mode,
    batch_size,
    enabled,
    status,
    created_at,
    updated_at
) VALUES
(
    '11111111-1111-1111-1111-111111111111',
    'film_dim_full',
    $$SELECT
          fw.id        AS film_id,
          fw.title     AS title,
          fw.rating    AS rating,
          NOW()        AS updated_at
      FROM content.film_work fw$$,
    'analytics.film_dim',
    'full',
    500,
    TRUE,
    'IDLE',
    NOW(),
    NOW()
),
(
    '22222222-2222-2222-2222-222222222222',
    'film_rating_agg_full',
    $$SELECT
          r.film_id,
          AVG(r.rating)::NUMERIC(3, 2) AS avg_rating,
          COUNT(*)::INT                AS votes_count,
          NOW()                        AS updated_at
      FROM ugc.ratings r
      GROUP BY r.film_id$$,
    'analytics.film_rating_agg',
    'full',
    500,
    TRUE,
    'IDLE',
    NOW(),
    NOW()
)
ON CONFLICT (id) DO UPDATE
SET
    name         = EXCLUDED.name,
    source_query = EXCLUDED.source_query,
    target_table = EXCLUDED.target_table,
    mode         = EXCLUDED.mode,
    batch_size   = EXCLUDED.batch_size,
    enabled      = EXCLUDED.enabled,
    status       = EXCLUDED.status,
    updated_at   = NOW();
