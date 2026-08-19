import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from backend.app.core.settings import LOG_DIR


def configure_logging():
    root = logging.getLogger()
    if root.handlers:
        return

    log_file = Path(LOG_DIR) / "backend.log"

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    rotating = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    rotating.setFormatter(formatter)

    root.setLevel(logging.INFO)
    root.addHandler(console)
    root.addHandler(rotating)

    for name in ["backend.api", "backend.ingestion", "backend.chat", "backend.web_search", "backend.system"]:
        logging.getLogger(name).setLevel(logging.INFO)
