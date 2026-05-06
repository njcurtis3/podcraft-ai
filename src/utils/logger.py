"""Structured logger for podcraft-ai. Import `logger` everywhere instead of using print."""

import logging
import sys


def _build_logger() -> logging.Logger:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
    )
    log = logging.getLogger("podcraft")
    log.setLevel(logging.DEBUG)
    if not log.handlers:
        log.addHandler(handler)
    log.propagate = False
    return log


logger = _build_logger()
