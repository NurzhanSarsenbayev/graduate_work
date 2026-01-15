from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Protocol
from uuid import UUID

from elasticsearch import AsyncElasticsearch
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.constants import ES_TARGET_PREFIX, is_allowed_target
from src.runner.ports.pipeline import PipelineLike


class Writer(Protocol):
    async def write(
        self,
        session: AsyncSession,
        pipeline: PipelineLike,
        rows: list[dict],
    ) -> int: ...


# ----------------------------
# Postgres
# ----------------------------

class PostgresWriter:
    async def write(
        self,
        session: AsyncSession,
        pipeline: PipelineLike,
        rows: list[dict],
    ) -> int:
        if not rows:
            return 0

        target = (pipeline.target_table or "").strip()

        if not is_allowed_target(target):
            raise ValueError(f"target_table '{target}' is not allowed")

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
                {"film_id": r["film_id"],
                 "title": r["title"], "rating": r.get("rating")}
                for r in rows
            ]
            await session.execute(insert_sql, payload)
            return len(payload)

        if target == "analytics.film_rating_agg":
            insert_sql = text(
                """
                INSERT INTO analytics.film_rating_agg
                 (film_id, avg_rating, rating_count)
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
                    "film_id": r["film_id"],
                    "avg_rating": r["avg_rating"],
                    "rating_count": r["rating_count"],
                }
                for r in rows
            ]
            await session.execute(insert_sql, payload)
            return len(payload)

        raise ValueError(f"Unsupported target_table"
                         f" for PostgresWriter: {target}")


# ----------------------------
# Elasticsearch
# ----------------------------

@dataclass(frozen=True, slots=True)
class ESConfig:
    url: str
    user: str | None
    password: str | None
    timeout: int = 10


def _load_es_config() -> ESConfig:
    return ESConfig(
        url=os.getenv("ELASTICSEARCH_URL", "http://elasticsearch:9200"),
        user=(os.getenv("ELASTICSEARCH_USER") or None),
        password=(os.getenv("ELASTICSEARCH_PASSWORD") or None),
        timeout=int(os.getenv("ELASTICSEARCH_TIMEOUT", "10")),
    )


def _jsonify(v):
    if v is None:
        return None
    if isinstance(v, UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _normalize_row(row: dict) -> dict:
    d = dict(row)  # RowMapping -> dict
    return {k: _jsonify(val) for k, val in d.items()}


class ElasticsearchWriter:
    """Upsert rows into Elasticsearch using bulk update (doc_as_upsert)."""

    def __init__(self, cfg: ESConfig) -> None:
        self._cfg = cfg

    def _index_from_target(self, target_table: str) -> str:
        # target_table like "es:film_dim"
        if not target_table.startswith(ES_TARGET_PREFIX):
            raise ValueError(
                f"ES writer expects target_table starting "
                f"with {ES_TARGET_PREFIX!r}, got {target_table!r}"
            )
        idx = target_table.removeprefix(ES_TARGET_PREFIX).strip()
        if not idx:
            raise ValueError("ES index is empty."
                             " Use target_table like 'es:film_dim'")
        return idx

    def _id_field_for_index(self, index: str) -> str:
        # MVP: document id field is film_id
        return "film_id"

    def _mappings_for_index(self, index: str) -> dict:
        # MVP mappings for demo
        if index == "film_dim":
            return {
                "mappings": {
                    "properties": {
                        "film_id": {"type": "keyword"},
                        "title": {"type": "text",
                                  "fields": {"raw": {"type": "keyword"}}},
                        "rating": {"type": "float"},
                    }
                }
            }

        if index == "film_rating_agg":
            return {
                "mappings": {
                    "properties": {
                        "film_id": {"type": "keyword"},
                        "avg_rating": {"type": "float"},
                        "rating_count": {"type": "integer"},
                    }
                }
            }

        # Fallback: dynamic mapping
        return {"mappings": {"dynamic": True}}

    async def _ensure_index(
            self,
            client: AsyncElasticsearch,
            index: str) -> None:
        if await client.indices.exists(index=index):
            return
        body = self._mappings_for_index(index)
        await client.indices.create(index=index, **body)

    async def write(
            self,
            session: AsyncSession,
            pipeline: PipelineLike,
            rows: list[dict]) -> int:
        if not rows:
            return 0

        target = (pipeline.target_table or "").strip()

        if not is_allowed_target(target):
            raise ValueError(f"target_table '{target}' is not allowed")

        index = self._index_from_target(target)
        id_field = self._id_field_for_index(index)

        auth = None
        if self._cfg.user:
            auth = (self._cfg.user, self._cfg.password or "")

        client = AsyncElasticsearch(
            hosts=[self._cfg.url],
            basic_auth=auth,
            request_timeout=self._cfg.timeout,
        )

        try:
            await self._ensure_index(client, index)

            ops: list[dict] = []
            for raw in rows:
                r = _normalize_row(raw)

                if id_field not in r:
                    raise ValueError(
                         f"ES writer expects field {id_field!r} in row. "
                         f"Row keys={list(r.keys())}"
                    )

                _id = str(r[id_field])

                ops.append({"update": {"_index": index, "_id": _id}})
                ops.append({"doc": r, "doc_as_upsert": True})

            resp = await client.bulk(operations=ops, refresh=False)

            if resp.get("errors"):
                items = resp.get("items") or []
                first_err = None
                for it in items:
                    v = (it.get("update") or it.get("index")
                         or it.get("create") or it.get("delete"))
                    if v and v.get("error"):
                        first_err = v
                        break
                raise RuntimeError(f"Elasticsearch bulk errors=True."
                                   f" first_error={first_err!r}")

            return len(rows)
        finally:
            await client.close()


# ----------------------------
# Resolver
# ----------------------------

def resolve_writer(pipeline: PipelineLike) -> Writer:
    target = (pipeline.target_table or "").strip()

    if target.startswith(ES_TARGET_PREFIX):
        return ElasticsearchWriter(_load_es_config())

    return PostgresWriter()
