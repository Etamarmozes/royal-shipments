from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from ..config import settings


def setup_logging() -> None:
    settings.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    handlers: list[logging.Handler] = [
        logging.StreamHandler(),
        RotatingFileHandler(
            settings.LOGS_DIR / "app.log",
            maxBytes=5_000_000,
            backupCount=5,
            encoding="utf-8",
        ),
    ]
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        handlers=handlers,
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
