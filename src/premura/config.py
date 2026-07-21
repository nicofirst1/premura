"""Settings: paths, encryption recipient, rclone remote, per-parser overrides.

Precedence (high to low): env var > XDG config file > field default.
Override any field via env var: PREMURA_DATA_DIR=/tmp/x, PREMURA_RCLONE_REMOTE=mygdrive, …
Nested fields use a double underscore: PREMURA_PARSERS__BMT__WEIGHT_UNIT=lb.
Personal, machine-local config (e.g. the backup folder id) belongs in the XDG
config file ~/.config/premura/config.toml, not in this checked-in file — same
convention as data under ~/.local/share/premura. Example config.toml:
    rclone_remote = "gdrive,root_folder_id=<drive-folder-id>"
    rclone_backup_prefix = ""
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # …/premura

# Durable, XDG-respecting home for user data and config. The warehouse must NOT
# default into the checkout: when the MCP server is launched via `uvx` its code
# lives in uv's disposable cache, so a repo-relative default would put private
# health data somewhere uv can garbage-collect. XDG paths persist across every
# launch regardless of how the server was started. Override with
# PREMURA_DATA_DIR / PREMURA_CONFIG_DIR.
_XDG_DATA_HOME = Path(os.environ.get("XDG_DATA_HOME") or Path.home() / ".local" / "share")
_XDG_CONFIG_HOME = Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")
_DATA_HOME = _XDG_DATA_HOME / "premura"
_CONFIG_HOME = _XDG_CONFIG_HOME / "premura"


class BmtParserSettings(BaseModel):
    weight_unit: Literal["kg", "lb"] = "kg"
    length_unit: Literal["cm", "in"] = "cm"


class ParserSettings(BaseModel):
    bmt: BmtParserSettings = Field(default_factory=BmtParserSettings)


class Settings(BaseSettings):
    """Top-level config for premura."""

    model_config = SettingsConfigDict(
        env_prefix="PREMURA_",
        env_nested_delimiter="__",
        extra="ignore",
        toml_file=_CONFIG_HOME / "config.toml",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        # High to low: explicit init args > env vars > XDG config.toml > defaults.
        return (
            init_settings,
            env_settings,
            TomlConfigSettingsSource(settings_cls),
            file_secret_settings,
        )

    # --- paths ---
    data_dir: Path = Field(default=_DATA_HOME)
    config_dir: Path = Field(default=_CONFIG_HOME)
    # Logs stay under the macOS convention (launchd integration writes here).
    log_dir: Path = Field(default=Path.home() / "Library" / "Logs" / "premura")

    # --- encryption ---
    age_recipients_file: Path = Field(default=_CONFIG_HOME / "recipients.txt")
    age_key_file: Path = Field(default=_CONFIG_HOME / "age.key")

    # --- upload ---
    # Generic fallbacks. The real destination is set per-machine in
    # config.toml — pin it by Drive folder ID (rclone connection string) so a
    # rename/move can't silently reroute backups; see module docstring.
    rclone_remote: str = Field(default="gdrive")
    rclone_backup_prefix: str = Field(default="Projects/Data/Health Data")

    # --- parser settings ---
    parsers: ParserSettings = Field(default_factory=ParserSettings)

    # --- launchd ---
    launchd_label: str = Field(default="com.nbrandizzi.premura.monthly")

    # --- derived paths ---
    @property
    def inbox_dir(self) -> Path:
        return self.data_dir / "inbox"

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def duck_dir(self) -> Path:
        return self.data_dir / "duck"

    @property
    def warehouse_path(self) -> Path:
        return self.duck_dir / "health.duckdb"

    @property
    def session_log_path(self) -> Path:
        """The session log's own DuckDB file (sibling of warehouse_path).

        A separate file from the health warehouse so the operating-session log
        and the health facts never share a writer (FR-070). Real runs default
        here; sandboxes override the path per isolation tag.
        """
        return self.duck_dir / "session_log.duckdb"

    @property
    def exports_dir(self) -> Path:
        return self.data_dir / "exports"

    @property
    def ready_sentinel(self) -> Path:
        return self.inbox_dir / ".ready"

    def ensure_dirs(self) -> None:
        for p in (
            self.data_dir,
            self.inbox_dir,
            self.raw_dir,
            self.duck_dir,
            self.exports_dir,
            self.log_dir,
        ):
            p.mkdir(parents=True, exist_ok=True)


settings = Settings()
