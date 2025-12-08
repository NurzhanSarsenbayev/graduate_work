SET search_path TO analytics, public;

-- Денормализованная витрина по фильмам
CREATE TABLE IF NOT EXISTS film_dim (
    film_id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    rating NUMERIC(3, 1),
    -- позже можно добавить genres, persons и т.п.
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Агрегаты рейтингов по фильмам
CREATE TABLE IF NOT EXISTS film_rating_agg (
    film_id UUID PRIMARY KEY,
    avg_rating NUMERIC(3, 2),
    votes_count INTEGER,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
