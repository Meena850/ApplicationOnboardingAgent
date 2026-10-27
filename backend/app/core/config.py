from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BACKEND_DIR / ".env", extra="ignore")

    app_name: str = "Application Onboarding Agent"
    environment: str = "development"
    log_level: str = "INFO"
    cors_origins: List[str] = ["http://localhost:5173"]
    data_dir: str = "../data"
    reports_dir: str = "../reports"
    llm_api_key: str | None = None

    # Azure OpenAI (Feature Understanding Agent)
    azure_openai_endpoint: str | None = None
    azure_openai_api_key: str | None = None
    azure_openai_deployment: str | None = None  # deployment name of your chat model
    azure_openai_api_version: str = "2024-10-21"
    azure_openai_timeout: float = 120.0
    azure_openai_max_context_chars: int = 60000
    @model_validator(mode="after")
    def _resolve_paths(self) -> "Settings":
        # Relative paths are anchored to the backend folder, not the process cwd.
        for field in ("data_dir", "reports_dir"):
            p = Path(getattr(self, field))
            setattr(self, field, str((p if p.is_absolute() else BACKEND_DIR / p).resolve()))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
