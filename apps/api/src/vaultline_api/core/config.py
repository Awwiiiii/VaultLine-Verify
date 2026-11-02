"""Validated application settings."""

from decimal import Decimal
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration loaded from environment variables or a local .env file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "VaultLine Verify API"
    environment: str = "development"
    cors_allowed_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    evidence_storage_dir: Path = Path(__file__).resolve().parents[5] / ".local/evidence"
    max_upload_bytes: int = Field(default=10 * 1024 * 1024, gt=0, le=50 * 1024 * 1024)

    verification_amount_tolerance: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )
    verification_quantity_tolerance: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )
    verification_price_tolerance: Decimal = Field(
        default=Decimal("0"), ge=0, max_digits=18, decimal_places=8, allow_inf_nan=False
    )

    database_host: str = "localhost"
    database_port: int = Field(default=5433, gt=0, le=65535)
    database_name: str = "vaultline_verify"
    database_user: str = "vaultline_app"
    database_password: str = ""
    database_url_override: str | None = None

    @property
    def database_url(self) -> str:
        """Build a safely escaped PostgreSQL URL, allowing an explicit URL override."""
        if self.database_url_override:
            return self.database_url_override
        user = quote_plus(self.database_user)
        password = quote_plus(self.database_password)
        credentials = f"{user}:{password}@" if self.database_password else f"{user}@"
        return (
            f"postgresql+psycopg://{credentials}{self.database_host}:"
            f"{self.database_port}/{self.database_name}"
        )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def split_origins(cls, value: object) -> object:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value

    @field_validator("environment")
    @classmethod
    def validate_environment(cls, value: str) -> str:
        allowed = {"development", "test", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"environment must be one of: {', '.join(sorted(allowed))}")
        return value


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached process settings."""
    return Settings()
