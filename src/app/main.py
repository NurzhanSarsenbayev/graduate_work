from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from infra.db import engine
from src.app.api.v1.pipelines import router as pipelines_router
from src.config import get_settings

logger = logging.getLogger("etl_api")
settings = get_settings()


async def wait_for_db(
    *,
    attempts: int = 10,
    delays: tuple[float, ...] = (1, 2, 4, 8, 8, 8, 8, 8, 8, 8),
) -> None:
    last_exc: Exception | None = None

    for i in range(1, attempts + 1):
        try:
            async with engine.connect() as conn:  # type: AsyncConnection
                await conn.execute(text("SELECT 1"))
            logger.info("DB connection OK on startup")
            return
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            delay = delays[i - 1] if i - 1 < len(delays) else delays[-1]
            logger.warning("DB not ready (%d/%d). Retrying in %ss... err=%r", i, attempts, delay, exc)
            await asyncio.sleep(delay)

    logger.exception("DB did not become ready after %d attempts", attempts)
    raise last_exc  # type: ignore[misc]


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    await wait_for_db()

    yield

    # shutdown
    await engine.dispose()
    logger.info("DB engine disposed")


app = FastAPI(title="ETL Platform API", version="0.1.0", lifespan=lifespan)
app.include_router(pipelines_router)


@app.get("/api/v1/health", tags=["system"])
async def healthcheck() -> dict:
    return {"status": "ok", "db": "ok", "env": settings.app_env}

