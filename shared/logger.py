"""
=========================================================
Office Automation Suite - Karina (OAS-K)
---------------------------------------------------------
File        : logger.py
Module      : Shared
Version     : 1.0.0
Author      : OpenAI & Zulkarnain Shiddiq
Python      : 3.14+
=========================================================

Centralized logging service.

Provides a singleton logger shared across all OAS-K modules.

=========================================================
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from config.logging_config import (
    BACKUP_LOG_COUNT,
    CREATE_LOG_FOLDER_IF_NOT_EXISTS,
    DATE_FORMAT,
    ENABLE_CONSOLE_LOG,
    ENABLE_FILE_LOG,
    ENABLE_ROTATING_LOG,
    LOG_FILE_PATH,
    LOG_FORMAT,
    LOG_LEVEL,
    MAX_LOG_FILE_SIZE,
)

# =========================================================
# LOGGER CACHE
# =========================================================

_LOGGER_CACHE: dict[str, logging.Logger] = {}


# =========================================================
# PRIVATE
# =========================================================

def _log_level() -> int:
    """
    Convert configured log level string to logging constant.
    """

    return getattr(logging, LOG_LEVEL.upper(), logging.INFO)


# =========================================================
# PUBLIC
# =========================================================

def get_logger(name: str) -> logging.Logger:
    """
    Return singleton logger.

    Parameters
    ----------
    name : str
        Logger name.

    Returns
    -------
    logging.Logger
    """

    if name in _LOGGER_CACHE:
        return _LOGGER_CACHE[name]

    if CREATE_LOG_FOLDER_IF_NOT_EXISTS:
        Path(LOG_FILE_PATH).parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    logger = logging.getLogger(name)
    logger.setLevel(_log_level())
    logger.propagate = False

    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        LOG_FORMAT,
        DATE_FORMAT,
    )

    # =====================================================
    # FILE HANDLER
    # =====================================================

    if ENABLE_FILE_LOG:

        if ENABLE_ROTATING_LOG:

            file_handler = RotatingFileHandler(
                filename=LOG_FILE_PATH,
                maxBytes=MAX_LOG_FILE_SIZE,
                backupCount=BACKUP_LOG_COUNT,
                encoding="utf-8",
            )

        else:

            file_handler = logging.FileHandler(
                filename=LOG_FILE_PATH,
                encoding="utf-8",
            )

        file_handler.setFormatter(formatter)

        logger.addHandler(file_handler)

    # =====================================================
    # CONSOLE HANDLER
    # =====================================================

    if ENABLE_CONSOLE_LOG:

        console_handler = logging.StreamHandler()

        console_handler.setFormatter(formatter)

        logger.addHandler(console_handler)

    _LOGGER_CACHE[name] = logger

    return logger