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

    # Webhook auth. Blank (the default) disables signature verification, so the
    # API is easy to hit locally with no setup; set it to require a valid
    # HMAC-SHA256 signature on inbound webhook requests.
    webhook_secret: str = Field(default="", alias="SENTINEL_WEBHOOK_SECRET")

    # Paths (carried on the settings object for convenience)
    runbooks_dir: Path = RUNBOOKS_DIR
    fixtures_dir: Path = FIXTURES_DIR

    # Where the incident store persists its SQLite database. Unlike
    # runbooks_dir/fixtures_dir (fixed repo content), this is deployment-specific
    # (e.g. a mounted volume path in Docker), so it's env-configurable.
    db_path: Path = Field(default=ROOT_DIR / "sentinel.db", alias="SENTINEL_DB_PATH")

    # Runbook retrieval. Off by default: the heuristic keyword/tag/service
    # scorer needs no extra dependencies. Set true for local sentence-transformer
    # embedding-based retrieval instead -- requires `pip install -e ".[embeddings]"`.
    use_embeddings: bool = Field(default=False, alias="SENTINEL_USE_EMBEDDINGS")
    embedding_model: str = Field(
        default="sentence-transformers/all-MiniLM-L6-v2", alias="SENTINEL_EMBEDDING_MODEL"
    )

    @property
    def llm_enabled(self) -> bool:
        """True when a real Anthropic key is present; otherwise use the fallback."""
        return bool(self.anthropic_api_key.strip())

    @property
    def webhook_auth_enabled(self) -> bool:
        """True when a webhook secret is configured; otherwise auth is skipped."""
        return bool(self.webhook_secret.strip())


@lru_cache
def get_settings() -> Settings:
    """Return cached settings."""
    return Settings()
