"""Runtime settings, overridable by environment variables."""

from __future__ import annotations

import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path


def _env_float(name: str, default: float) -> float:
    return float(os.environ.get(name, default))


@dataclass
class Settings:
    workspace: Path = field(default_factory=lambda: Path("workspace"))
    models_path: Path = field(default_factory=lambda: Path("config/models.yaml"))
    lmstudio_url: str = "http://localhost:1234"
    timeout: float = 300.0
    load_timeout: float = 600.0
    max_revisions: int = 3
    lms_bin: str | None = None

    @classmethod
    def from_env(cls) -> Settings:
        return cls(
            workspace=Path(os.environ.get("AIO_WORKSPACE", "workspace")),
            models_path=Path(os.environ.get("AIO_MODELS", "config/models.yaml")),
            lmstudio_url=os.environ.get("AIO_LMSTUDIO_URL", "http://localhost:1234"),
            timeout=_env_float("AIO_TIMEOUT", 300.0),
            load_timeout=_env_float("AIO_LOAD_TIMEOUT", 600.0),
            max_revisions=int(os.environ.get("AIO_MAX_REVISIONS", 3)),
            lms_bin=os.environ.get("AIO_LMS_BIN") or shutil.which("lms"),
        )
