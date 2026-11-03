"""Typed application settings, read from ROSEHILL_* environment variables and `.env`.

Each milestone adds the settings it needs. Business rules such as fee rates are
stored in the database and edited from the Settings page; values here are
process-level configuration and first-run defaults.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ROSEHILL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/rosehill.db"
    source_base_url: str = "https://rosehillonline.ca"
    timezone: str = "America/Toronto"
    request_interval_seconds: float = Field(default=2.0, ge=1.0)
    user_agent: str = "rosehill-auction-manager/0.1 (personal use)"

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value
