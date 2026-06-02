import logging
import os
import sys
from typing import TextIO


LOGGER_NAME = "mabimo"
DEFAULT_LOG_LEVEL = "DEBUG"
_CONSOLE_HANDLER_NAME = "mabimo-console"


def get_logger(name: str | None = None) -> logging.Logger:
    configure_logger()
    if not name:
        return logging.getLogger(LOGGER_NAME)
    return logging.getLogger(f"{LOGGER_NAME}.{name}")


def configure_logger(
    *,
    level_name: str | None = None,
    stream: TextIO | None = None,
) -> logging.Logger:
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(_resolve_level(level_name or os.getenv("LOG_LEVEL")))
    logger.propagate = False

    handler = _find_console_handler(logger)
    if handler is None:
        handler = logging.StreamHandler(stream or sys.stdout)
        handler.name = _CONSOLE_HANDLER_NAME
        logger.addHandler(handler)
    elif stream is not None:
        handler.setStream(stream)

    handler.setLevel(logging.DEBUG)
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    return logger


def _find_console_handler(logger: logging.Logger) -> logging.Handler | None:
    for handler in logger.handlers:
        if handler.name == _CONSOLE_HANDLER_NAME:
            return handler
    return None


def _resolve_level(level_name: str | None) -> int:
    if not level_name:
        level_name = DEFAULT_LOG_LEVEL

    level = getattr(logging, level_name.strip().upper(), None)
    if isinstance(level, int):
        return level
    return logging.DEBUG
