"""Logging to stderr and a workspace file. Never stdout (stdout is the MCP stdio channel)."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

LOGGER = "ai_orchestrator"


def setup_logging(workspace: Path, level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(LOGGER)
    if logger.handlers:
        return logger
    logger.setLevel(level)
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(message)s")
    err = logging.StreamHandler(sys.stderr)
    err.setFormatter(fmt)
    logger.addHandler(err)
    try:
        Path(workspace).mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(Path(workspace) / "orchestrator.log", encoding="utf-8")
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except OSError:
        pass
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger(LOGGER)
