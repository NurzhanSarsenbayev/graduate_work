SET search_path TO ugc, public;

CREATE TABLE IF NOT EXISTS ratings (
    id UUID PRIMARY KEY,
    film_id UUID NOT NULL,
    user_id UUID NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 10),
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
