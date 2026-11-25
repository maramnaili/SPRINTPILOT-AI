from sprintpilot import __version__
from sprintpilot.config import Settings, create_llm_client


def test_package_version() -> None:
    assert __version__ == "0.1.0"


def test_default_settings_are_safe_for_local_development() -> None:
    settings = Settings()

    assert settings.app_env == "development"
    assert settings.ollama_base_url == "http://localhost:11434/v1"
    assert settings.ollama_model == "qwen2.5:3b"
    assert settings.ollama_timeout_seconds == 300
    assert settings.database_url == "sqlite:///./data/sprintpilot.db"


def test_llm_client_uses_local_ollama() -> None:
    client = create_llm_client()

    assert str(client.base_url).rstrip("/") == "http://localhost:11434/v1"
    assert client.api_key == "ollama"
