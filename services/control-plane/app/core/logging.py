"""Structured logging helpers."""

from __future__ import annotations

import logging
import sys
from typing import Any

from app.core.config import get_settings


def configure_logging() -> None:
    settings = get_settings()
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
        stream=sys.stdout,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)


def log_extra(**kwargs: Any) -> dict[str, Any]:
    return kwargs
