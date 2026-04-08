from __future__ import annotations

import json
import logging
import sys
from logging.handlers import RotatingFileHandler
from typing import Any, Optional

from oscilloscope_backend.utils.config import Settings, get_settings


class JsonLineFormatter(logging.Formatter):
    """One JSON object per line for file sinks (parseable by log aggregators)."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "ts": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


def setup_logging(
    level: Optional[str] = None,
    *,
    settings: Optional[Settings] = None,
    name: Optional[str] = None,
) -> logging.Logger:
    """
    Configure root logging: human-readable console + optional rotating file.

    Debug messages appear when ``log_level`` is DEBUG. File receives the same levels.
    """
    st = settings or get_settings()
    log_level = level or st.log_level
    numeric = getattr(logging, log_level.upper(), logging.INFO)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(numeric)

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(numeric)
    console.setFormatter(
        logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(console)

    if st.log_file_enabled:
        path = st.resolved_log_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        fh = RotatingFileHandler(
            path,
            maxBytes=st.log_max_bytes,
            backupCount=st.log_backup_count,
            encoding="utf-8",
        )
        fh.setLevel(numeric)
        if st.log_json_file:
            fh.setFormatter(JsonLineFormatter(datefmt="%Y-%m-%dT%H:%M:%S"))
        else:
            fh.setFormatter(
                logging.Formatter(
                    "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
            )
        root.addHandler(fh)

    logger = logging.getLogger(name or "oscilloscope")
    logger.setLevel(numeric)
    return logger
