from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.constants import ALLOWED_TARGET_TABLES
from src.app.models import EtlPipeline


async def write_target_table(
    session: AsyncSession,
    pipeline: EtlPipeline,
    rows: list[dict],
) -> int:
    """Записать данные в целевую таблицу в зависимости от pipeline.target_table."""
    target = pipeline.target_table

    if target not in ALLOWED_TARGET_TABLES:
        raise ValueError(
            f"Unsupported target_table={target!r}. "
            f"Allowed: {sorted(ALLOWED_TARGET_TABLES)}"
        )

    if target == "analytics.film_dim":
        insert_sql = text(
            """
            INSERT INTO analytics.film_dim (film_id, title, rating)
            VALUES (:film_id, :title, :rating)
            ON CONFLICT (film_id) DO UPDATE
            SET
                title = EXCLUDED.title,
                rating = EXCLUDED.rating,
                updated_at = NOW()
            """
        )

        written = 0
        for row in rows:
            await session.execute(
                insert_sql,
                {
                    "film_id": row["film_id"],
                    "title": row["title"],
                    "rating": row.get("rating"),
                },
            )
            written += 1
        return written

    if target == "analytics.film_rating_agg":
        insert_sql = text(
            """
            INSERT INTO analytics.film_rating_agg (film_id, avg_rating, rating_count)
            VALUES (:film_id, :avg_rating, :rating_count)
            ON CONFLICT (film_id) DO UPDATE
            SET
                avg_rating = EXCLUDED.avg_rating,
                rating_count = EXCLUDED.rating_count,
                updated_at = NOW()
            """
        )

        written = 0
        for row in rows:
            await session.execute(
                insert_sql,
                {
                    "film_id": row["film_id"],
                    "avg_rating": row["avg_rating"],
                    "rating_count": row["rating_count"],
                },
            )
            written += 1
        return written

    # Сюда мы уже не должны попадать, но safety net оставим
    raise ValueError(f"Unsupported target_table for SQL full pipeline: {target}")
