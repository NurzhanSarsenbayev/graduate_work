from fastapi import FastAPI

from src.config import get_settings
from src.app.db import engine
from src.app.api.v1.pipelines import router as pipelines_router

settings = get_settings()

app = FastAPI(title="ETL Platform API", version="0.1.0")
app.include_router(pipelines_router)


@app.on_event("startup")
async def on_startup() -> None:
    # Проверяем, что до БД можно достучаться
    try:
        async with engine.connect() as conn:  # type: AsyncConnection
            await conn.execute("SELECT 1")
    except Exception as exc:  # noqa: BLE001
        # TODO: нормальное логирование
        print(f"DB connection failed on startup: {exc}")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    await engine.dispose()


@app.get("/api/v1/health", tags=["system"])
async def healthcheck() -> dict:
    return {
        "status": "ok",
        "db": "ok",  # позже можно реально проверять запросом
        "env": settings.app_env,
    }
