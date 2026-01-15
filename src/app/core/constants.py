from __future__ import annotations

ALLOWED_TARGET_TABLES: set[str] = {
    "analytics.film_dim",
    "analytics.film_rating_agg",
}

ES_TARGET_PREFIX = "es:"

# MVP: only allowing these indexes - for security
ALLOWED_ES_INDEXES: set[str] = {
    "film_dim",
    "film_rating_agg",
}


def is_allowed_target(target: str) -> bool:
    target = (target or "").strip()

    if target in ALLOWED_TARGET_TABLES:
        return True

    if target.startswith(ES_TARGET_PREFIX):
        idx = target.removeprefix(ES_TARGET_PREFIX).strip()
        return bool(idx) and idx in ALLOWED_ES_INDEXES

    return False
