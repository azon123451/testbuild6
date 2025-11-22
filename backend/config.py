from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = Field("sqlite:///./support.db", alias="DATABASE_URL")
    bot_api_token: str = Field(..., alias="BACKEND_API_TOKEN")
    operator_history_token: str = Field(..., alias="OPERATOR_HISTORY_TOKEN")
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"], alias="ALLOWED_ORIGINS")


@lru_cache
def get_settings() -> Settings:
    return Settings()

