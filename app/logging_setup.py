"""Strukturované a rotované logování bez osobních údajů."""

from __future__ import annotations

import json
import logging
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from zoneinfo import ZoneInfo

PRAGUE_TZ = ZoneInfo("Europe/Prague")


class StructuredJsonFormatter(logging.Formatter):
    """Formátuje log záznamy jako jednořádkový JSON v časové zóně Europe/Prague."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "timestamp": datetime.now(PRAGUE_TZ).isoformat(timespec="seconds"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        extra_fields = getattr(record, "structured_data", None)
        if isinstance(extra_fields, dict):
            payload.update(extra_fields)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Nastaví rotované logování do souboru i na standardní výstup."""
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "suplovani.log"

    logger = logging.getLogger("suplovani")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    formatter = StructuredJsonFormatter()

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    return logger
