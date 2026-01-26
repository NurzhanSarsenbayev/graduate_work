from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.config import get_settings

settings = get_settings()

# Async engine SQLAlchemy
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=False,
    future=True,
    pool_pre_ping=True,
    pool_recycle=1800,
)

# Session factory
async_session_factory = async_sessionmaker(
    engine,
    expire_on_commit=False,
)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """DI-dependency for FastAPI: AsyncSession."""
    async with async_session_factory() as session:
        yield session
