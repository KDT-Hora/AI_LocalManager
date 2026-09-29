"""Load and hot-reload config/models.yaml."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError

from ..models.model_definition import ModelDefinition, ModelsConfig


class RegistryError(Exception):
    pass


def load_config(path: Path) -> ModelsConfig:
    path = Path(path)
    if not path.exists():
        raise RegistryError(f"models file not found: {path}")
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        return ModelsConfig.model_validate(data)
    except yaml.YAMLError as e:
        raise RegistryError(f"{path}: invalid YAML: {e}") from e
    except ValidationError as e:
        lines = [f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors()]
        raise RegistryError(f"{path}: " + "; ".join(lines)) from e


class ModelRegistry:
    """Re-reads the YAML when its mtime changes, so edits apply without restart (FR-014)."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)
        self._mtime: float | None = None
        self._config = ModelsConfig()

    def config(self) -> ModelsConfig:
        mtime = self.path.stat().st_mtime_ns if self.path.exists() else None
        if mtime != self._mtime:
            self._config = load_config(self.path)
            self._mtime = mtime
        return self._config

    def get(self, model_id: str) -> ModelDefinition | None:
        return next((m for m in self.config().models if m.id == model_id), None)
