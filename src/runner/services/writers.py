from __future__ import annotations

from typing import Protocol

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.constants import ALLOWED_TARGET_TABLES
from src.app.models import EtlPipeline


class Writer(Protocol):
    async def write(
        self,
        session: AsyncSession,
        pipeline: EtlPipeline,
        rows: list[dict],
    ) -> int: ...


class PostgresWriter:
    async def write(
        self,
        session: AsyncSession,
        pipeline: EtlPipeline,
        rows: list[dict],
    ) -> int:
        """Записать данные в Postgres-таблицу (analytics.*) согласно target_table."""
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

            payload = [
                {
                    "film_id": row["film_id"],
                    "title": row["title"],
                    "rating": row.get("rating"),
                }
                for row in rows
            ]
            await session.execute(insert_sql, payload)
            return len(payload)

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

            payload = [
                {
                    "film_id": row["film_id"],
                    "avg_rating": row["avg_rating"],
                    "rating_count": row["rating_count"],
                }
                for row in rows
            ]
            await session.execute(insert_sql, payload)
            return len(payload)

        # safety net (ALLOWED_TARGET_TABLES должен не дать попасть сюда)
        raise ValueError(f"Unsupported target_table for PostgresWriter: {target}")


def resolve_writer(pipeline: EtlPipeline) -> Writer:
    """Выбрать writer для пайплайна.

    Пока MVP: только Postgres sink.
    Позже: если появится sink_type/sink_config -> выбирать ElasticsearchWriter и т.п.
    """
    return PostgresWriter()


# ✅ Backward compatibility: старое имя функции остаётся
async def write_target_table(
    session: AsyncSession,
    pipeline: EtlPipeline,
    rows: list[dict],
) -> int:
    return await resolve_writer(pipeline).write(session, pipeline, rows)
