from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parents[2] / ".env"

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "OneDMS"
    VERSION: str = "0.1.0"
    DEBUG: bool = True
    API_PREFIX: str = "/api"
    DATABASE_URL: SecretStr = SecretStr("")
    AWS_ENDPOINT_URL_S3: str = ""
    AWS_REGION: str = "ap-southeast-1"
    AWS_ACCESS_KEY_ID: SecretStr = SecretStr("")
    AWS_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    S3_BUCKET_NAME: str = "assets"
    DEPENDENCY_TIMEOUT_SECONDS: float = Field(default=10, ge=1, le=60)
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]

    # OpenRouter AI Configuration
    OPENROUTER_API_KEY: SecretStr = SecretStr("")
    OPEN_ROUTER_KEY: SecretStr = SecretStr("")
    OPENROUTER_MODEL: str = "nvidia/nemotron-3-ultra-550b-a55b:free"
    OPENROUTER_FALLBACK_MODEL: str = "openrouter/free"
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"

    @property
    def openrouter_key(self) -> str:
        return self.OPENROUTER_API_KEY.get_secret_value() or self.OPEN_ROUTER_KEY.get_secret_value()

settings = Settings()
