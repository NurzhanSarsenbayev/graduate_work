from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "local"

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "etl_demo"
    db_user: str = "etl_user"
    db_password: str = "etl_password"

    @property
    def database_url(self) -> str:
        # asyncpg + SQLAlchemy 2.x
        return (
            f"postgresql+asyncpg://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
