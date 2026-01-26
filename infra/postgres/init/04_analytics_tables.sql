CREATE SCHEMA IF NOT EXISTS analytics;
SET search_path TO analytics, public;

-- Denormalized film dimension table
CREATE TABLE IF NOT EXISTS film_dim (
    film_id      UUID PRIMARY KEY,
    title        TEXT NOT NULL,
    rating       NUMERIC(3, 1),
    -- Future extension: genres, persons, etc.
    updated_at   TIMESTAMPTZ DEFAULT NOW()
);

-- Film rating aggregates
CREATE TABLE IF NOT EXISTS film_rating_agg (
    film_id       UUID PRIMARY KEY,
    avg_rating    NUMERIC(3, 2),
    rating_count  INTEGER,
    updated_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Optional analytics indexes
CREATE INDEX IF NOT EXISTS ix_film_dim_rating
    ON film_dim (rating);

CREATE INDEX IF NOT EXISTS ix_film_rating_agg_rating_count
    ON film_rating_agg (rating_count DESC);
