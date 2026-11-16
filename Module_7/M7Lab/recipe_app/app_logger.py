"""Configures file-based logging for the Recipe Management System.

Each run writes to its own timestamped file under logs/, e.g.
logs/recipes_2026-09-22_14-30-05.txt.
"""

import logging
from datetime import datetime

from app_paths import writable_path

LOG_DIR = writable_path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / datetime.now().strftime("recipes_%Y-%m-%d_%H-%M-%S.txt")


def get_logger(name):
    """Return a logger that writes timestamped entries to this run's log file."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.DEBUG)
        logger.propagate = False  # keep recipe logs out of other apps' log files
    return logger
