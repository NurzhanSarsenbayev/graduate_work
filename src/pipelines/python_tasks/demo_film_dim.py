from __future__ import annotations

from typing import Any


def transform(rows: list[dict], pipeline: Any = None) -> list[dict]:
    # example: normalize rating -> float|None, title -> str
    out: list[dict] = []
    for r in rows:
        rating = r.get("rating")
        out.append(
            {
                "film_id": r["film_id"],
                "title": str(r.get("title") or ""),
                "rating": float(rating) if rating is not None else None,
            }
        )
    return out
