"""Environment-driven configuration for Sentinel.

All settings have offline-friendly defaults so the full pipeline runs with zero
external dependencies. Real integrations are opted into by setting
``SENTINEL_USE_MOCKS=false`` and supplying the relevant credentials.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo root (…/sentinel/config.py -> repo root is two parents up).
ROOT_DIR = Path(__file__).resolve().parent.parent
RUNBOOKS_DIR = ROOT_DIR / "runbooks"
FIXTURES_DIR = ROOT_DIR / "fixtures"


class Settings(BaseSettings):
    """Runtime configuration, populated from environment / ``.env``.

    Our own knobs use a ``SENTINEL_`` prefix; third-party credentials keep their
    conventional bare names (e.g. ``ANTHROPIC_API_KEY``) via explicit aliases.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    # LLM
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    model: str = Field(default="claude-sonnet-5", alias="SENTINEL_MODEL")

    # Integration toggle
    use_mocks: bool = Field(default=True, alias="SENTINEL_USE_MOCKS")

    # Real-integration credentials (unused while use_mocks is true)
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_repo: str = Field(default="", alias="GITHUB_REPO")
    slack_bot_token: str = Field(default="", alias="SLACK_BOT_TOKEN")
    slack_channel: str = Field(default="", alias="SLACK_CHANNEL")

    # Paths (carried on the settings object for convenience)
    runbooks_dir: Path = RUNBOOKS_DIR
    fixtures_dir: Path = FIXTURES_DIR

    @property
    def llm_enabled(self) -> bool:
        """True when a real Anthropic key is present; otherwise use the fallback."""
        return bool(self.anthropic_api_key.strip())


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
