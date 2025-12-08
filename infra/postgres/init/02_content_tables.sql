SET search_path TO content, public;

CREATE TABLE IF NOT EXISTS film_work (
    id UUID PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    rating NUMERIC(3, 1),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- ОБЯЗАТЕЛЬНО потом добавим genre, person и связи
