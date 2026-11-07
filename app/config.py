"""Konfigurace aplikace načítaná z config.yaml a proměnných prostředí (.env)."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


class AppConfig(BaseModel):
    """Hlavní konfigurace Suplování Viewer."""

    watch_dir: Path = Field(default=Path("./watch_exports"))
    file_pattern: str = Field(default="*.htm*")
    db_path: Path = Field(default=Path("./data/suplovani.db"))
    log_dir: Path = Field(default=Path("./logs"))
    poll_interval_seconds: float = Field(default=30.0, ge=1.0)
    stability_seconds: float = Field(default=2.0, ge=0.0)
    retention_days: int = Field(default=14, ge=1)
    stale_threshold_hours: float = Field(default=24.0, ge=1.0)
    anonymize: bool = Field(default=False)
    max_file_size_bytes: int = Field(default=5 * 1024 * 1024, ge=1024)
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    admin_username: str = Field(default="admin")
    admin_password: str = Field(default="")
    admin_allowed_cidrs: list[str] = Field(
        default_factory=lambda: ["127.0.0.1/32", "::1/128", "10.0.0.0/8", "172.16.0.0/12", "192.168.0.0/16"]
    )
    teacher_codes: dict[str, str] = Field(default_factory=dict)
    upload_token: str = Field(default="")
    web_url: str = Field(default="https://klasifikace.skolakrizik.cz/next/zmeny.aspx")
    web_poll_interval_seconds: float = Field(default=300.0, ge=60.0)
    web_enabled: bool = Field(default=True)


def _parse_bool(val: str) -> bool:
    return val.strip().lower() in ("1", "true", "yes", "on", "ano")


def load_config(config_path: Path | None = None) -> AppConfig:
    """Načte konfiguraci z YAML souboru (pokud existuje) a přepíše ji proměnnými prostředí."""
    data: dict[str, Any] = {}

    cfg_file = config_path or Path(os.environ.get("SUPL_CONFIG_FILE", "config.yaml"))
    if cfg_file.is_file():
        loaded = yaml.safe_load(cfg_file.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            data.update(loaded)

    env_map: dict[str, tuple[str, Any]] = {
        "SUPL_WATCH_DIR": ("watch_dir", Path),
        "SUPL_FILE_PATTERN": ("file_pattern", str),
        "SUPL_DB_PATH": ("db_path", Path),
        "SUPL_LOG_DIR": ("log_dir", Path),
        "SUPL_POLL_INTERVAL_SECONDS": ("poll_interval_seconds", float),
        "SUPL_STABILITY_SECONDS": ("stability_seconds", float),
        "SUPL_RETENTION_DAYS": ("retention_days", int),
        "SUPL_STALE_THRESHOLD_HOURS": ("stale_threshold_hours", float),
        "SUPL_ANONYMIZE": ("anonymize", _parse_bool),
        "SUPL_MAX_FILE_SIZE_BYTES": ("max_file_size_bytes", int),
        "SUPL_HOST": ("host", str),
        "SUPL_PORT": ("port", int),
        "SUPL_ADMIN_USERNAME": ("admin_username", str),
        "SUPL_ADMIN_PASSWORD": ("admin_password", str),
        "SUPL_UPLOAD_TOKEN": ("upload_token", str),
        "SUPL_WEB_URL": ("web_url", str),
        "SUPL_WEB_POLL_INTERVAL_SECONDS": ("web_poll_interval_seconds", float),
        "SUPL_WEB_ENABLED": ("web_enabled", _parse_bool),
    }

    for env_key, (field_name, converter) in env_map.items():
        raw_val = os.environ.get(env_key)
        if raw_val is not None and raw_val != "":
            data[field_name] = converter(raw_val)

    cidrs_env = os.environ.get("SUPL_ADMIN_ALLOWED_CIDRS")
    if cidrs_env:
        data["admin_allowed_cidrs"] = [c.strip() for c in cidrs_env.split(",") if c.strip()]

    return AppConfig.model_validate(data)
