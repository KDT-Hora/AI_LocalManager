from __future__ import annotations

from typing import Protocol

from ..errors import UNSUPPORTED_BACKEND, OrchestratorError
from ..models.model_definition import ModelDefinition


class Backend(Protocol):
    async def prepare(
        self,
        model: ModelDefinition,
        previous: ModelDefinition | None = None,
        vram_limit_gb: float | None = None,
    ) -> None:
        """Make `model` ready (load it; unload `previous` if VRAM requires)."""

    async def chat(self, model: ModelDefinition, prompt: str) -> str:
        """Return the generated text."""


def ensure_supported(model: ModelDefinition) -> None:
    # Image generation needs a different runtime (research.md R4); not implemented in v1.
    if model.model_type == "image_gen" or model.output_format == "image":
        raise OrchestratorError(
            UNSUPPORTED_BACKEND,
            f"model '{model.id}' is an image generation model; no backend is available in v1",
        )
