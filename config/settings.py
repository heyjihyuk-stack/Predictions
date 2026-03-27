"""Application settings loaded from environment variables."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # LLM
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_MODEL: str = "gpt-4o"

    # News sources
    NEWSAPI_KEY: str = ""
    FINNHUB_KEY: str = ""

    # Flask
    FLASK_DEBUG: bool = False

    # Paths
    SOURCES_FILE: str = str(Path(__file__).resolve().parent / "sources.yaml")
    PROMPTS_DIR: str = str(Path(__file__).resolve().parent.parent / "prompts")


@lru_cache
def get_settings() -> Settings:
    return Settings()
