from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    operator_pins: List[str] = Field(default_factory=list, alias="OPERATOR_PINS")
    operator_max_concurrent: int = Field(1, alias="OPERATOR_MAX_CONCURRENT", ge=1, le=5)
    auto_reply_minutes: int = Field(2, alias="AUTO_REPLY_MINUTES", ge=1, le=30)
    auto_reply_text: str = Field(
        "Все операторы заняты, подключим вас в ближайшее время.", alias="AUTO_REPLY_TEXT"
    )
    backend_base_url: str = Field("http://localhost:8000", alias="BACKEND_BASE_URL")
    backend_api_token: str = Field(..., alias="BACKEND_API_TOKEN")


@lru_cache
def get_settings() -> Settings:
    return Settings()

