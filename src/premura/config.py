"""Settings: paths, encryption recipient, rclone remote, per-parser overrides.

Override any field via env var: PREMURA_DATA_DIR=/tmp/x, PREMURA_RCLONE_REMOTE=mygdrive, …
Nested fields use a double underscore: PREMURA_PARSERS__BMT__WEIGHT_UNIT=lb.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

REPO_ROOT = Path(__file__).resolve().parent.parent.parent  # …/premura


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
    )

    # --- paths ---
    data_dir: Path = Field(default=REPO_ROOT / "data")
    config_dir: Path = Field(default=Path.home() / ".config" / "premura")
    log_dir: Path = Field(default=Path.home() / "Library" / "Logs" / "premura")

    # --- encryption ---
    age_recipients_file: Path = Field(
        default=Path.home() / ".config" / "premura" / "recipients.txt"
    )
    age_key_file: Path = Field(default=Path.home() / ".config" / "premura" / "age.key")

    # --- upload ---
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
