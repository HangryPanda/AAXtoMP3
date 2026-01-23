"""Application configuration using Pydantic Settings."""

from enum import Enum
from functools import lru_cache
import json
from pathlib import Path
from typing import Literal

from pydantic import Field, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MoveFilesPolicy(str, Enum):
    """Policy for handling misplaced converted files during repair."""

    REPORT_ONLY = "report_only"  # Just log, don't move
    ALWAYS_MOVE = "always_move"  # Auto-move without prompting
    ASK_EACH = "ask_each"  # Return list for user confirmation


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Application
    app_name: str = "Audible Library Manager API"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1

    # Database
    database_url: str = Field(
        default="postgresql+asyncpg://audible:password@localhost:5432/audible_db",
        description="PostgreSQL connection URL",
    )
    database_echo: bool = False

    # Paths
    data_dir: Path = Field(default=Path("/data"), description="Base data directory")
    downloads_dir: Path = Field(default=Path("/data/downloads"), description="Downloaded AAX/AAXC files")
    converted_dir: Path = Field(default=Path("/data/converted"), description="Converted audio files")
    completed_dir: Path = Field(default=Path("/data/completed"), description="Moved source files after conversion")
    core_scripts_dir: Path = Field(default=Path("/core"), description="AAXtoMP3 scripts directory")
    manifest_dir: Path = Field(default=Path("/specs"), description="Manifest directory (download/converted/library cache)")

    # Audible
    audible_auth_file: Path = Field(
        default=Path.home() / ".audible" / "auth.json",
        description="Audible authentication file",
    )
    audible_profile: str = Field(default="default", description="Audible profile name")

    # Job Concurrency
    max_download_concurrent: int = Field(default=5, ge=1, le=10, description="Max concurrent downloads")
    max_convert_concurrent: int = Field(default=2, ge=1, le=4, description="Max concurrent conversions")

    # WebSocket
    ws_log_buffer_ms: int = Field(default=100, description="WebSocket log buffer interval in ms")
    ws_ping_interval: int = Field(default=30, description="WebSocket ping interval in seconds")

    # Repair
    move_files_policy: MoveFilesPolicy = Field(
        default=MoveFilesPolicy.REPORT_ONLY,
        description="How to handle misplaced converted files during repair",
    )
    repair_extract_metadata: bool = Field(
        default=True,
        description="Extract metadata (chapters, technical info) from M4B files during repair",
    )
    repair_delete_duplicates: bool = Field(
        default=False,
        description="Automatically delete duplicate conversions during repair (keeps best match)",
    )
    repair_update_manifests: bool = Field(
        default=True,
        description="Update download/converted manifests from filesystem during repair",
    )

    # Post-Conversion
    move_after_complete: bool = Field(
        default=False,
        description="Move source AAXC files to completed_dir after successful conversion",
    )

    # CORS
    # NOTE: Keep this as a string so pydantic-settings doesn't attempt JSON parsing
    # before our validators run (which breaks on comma-separated values).
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description='Allowed CORS origins (comma-separated or JSON array, e.g. \'["https://a","https://b"]\')',
    )

    @computed_field
    @property
    def cors_origins_list(self) -> list[str]:
        raw = (self.cors_origins or "").strip()
        if raw == "":
            return []
        if raw.startswith("["):
            try:
                parsed = json.loads(raw)
                if isinstance(parsed, list):
                    return [str(it).strip() for it in parsed if str(it).strip()]
            except json.JSONDecodeError:
                pass
        return [origin.strip() for origin in raw.split(",") if origin.strip()]

    @computed_field
    @property
    def aaxtomp3_path(self) -> Path:
        """Full path to AAXtoMP3 script."""
        # Use .resolve() to ensure the path is absolute
        return (self.core_scripts_dir / "AAXtoMP3").resolve()

    def ensure_directories(self) -> None:
        """Create required directories if they don't exist."""
        for directory in [self.downloads_dir, self.converted_dir, self.completed_dir]:
            directory.mkdir(parents=True, exist_ok=True)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
