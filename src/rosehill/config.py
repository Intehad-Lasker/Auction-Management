"""Typed application settings, read from ROSEHILL_* environment variables and `.env`.

Each milestone adds the settings it needs. Business rules such as fee rates are
stored in the database and edited from the Settings page; values here are
process-level configuration and first-run defaults.
"""

from decimal import Decimal
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
    source: str = "demo"
    source_base_url: str = "https://rosehillonline.ca"
    timezone: str = "America/Toronto"
    request_interval_seconds: float = Field(default=2.0, ge=1.0)
    user_agent: str = "rosehill-auction-manager/0.1 (personal use)"

    # How often lots are re-scraped. Lots closing sooner are checked more often.
    scheduler_tick_seconds: int = Field(default=60, ge=30)
    full_sweep_minutes: int = Field(default=60, ge=10)
    soon_within_minutes: int = Field(default=120, ge=1)
    soon_every_minutes: int = Field(default=5, ge=1)
    imminent_within_minutes: int = Field(default=15, ge=1)
    imminent_every_minutes: int = Field(default=1, ge=1)
    # A lot no longer listed this long after its closing time is recorded as closed.
    close_grace_minutes: int = Field(default=5, ge=1)

    # First-run fee defaults, used until real rates are saved on the Settings page.
    # Rosehill's actual buyer's premium is not confirmed yet; 13% is Ontario HST.
    default_premium_percent: Decimal = Field(default=Decimal("15"), ge=0)
    default_tax_percent: Decimal = Field(default=Decimal("13"), ge=0)

    @field_validator("timezone")
    @classmethod
    def _known_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError(f"unknown timezone: {value}") from exc
        return value
