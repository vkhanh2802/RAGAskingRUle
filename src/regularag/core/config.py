from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import PostgresDsn, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "regularag-api"
    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    database_url: PostgresDsn = PostgresDsn(
        "postgresql://regularag:regularag@localhost:5432/regularag"
    )
    database_connect_timeout_seconds: int = 3
    rag_config_path: Path = Path("configs/rag/baseline.json")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="REGULARAG_",
        extra="ignore",
    )

    @field_validator("database_connect_timeout_seconds")
    @classmethod
    def validate_database_timeout(cls, value: int) -> int:
        if value < 1:
            raise ValueError("database connect timeout must be at least one second")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
