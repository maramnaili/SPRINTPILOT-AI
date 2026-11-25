from openai import OpenAI
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = "qwen2.5:3b"
    ollama_timeout_seconds: int = Field(default=300, gt=0)
    app_env: str = "development"
    database_url: str = "sqlite:///./data/sprintpilot.db"
    chroma_persist_directory: str = "./data/chroma"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()


def create_llm_client() -> OpenAI:
    """Create an OpenAI-compatible client for the local Ollama server."""

    return OpenAI(
        base_url=settings.ollama_base_url,
        api_key="ollama",
        timeout=settings.ollama_timeout_seconds,
        max_retries=0,
    )
