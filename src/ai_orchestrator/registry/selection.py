"""Deterministic model selection (research.md R6)."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..errors import NO_CAPABLE_MODEL, OrchestratorError
from ..models.model_definition import ModelDefinition, ModelsConfig

DEFAULT_MAX_TOKENS = 2048


def estimate_tokens(prompt: str, model: ModelDefinition) -> int:
    """Conservative: chars / 2 rounded up, plus room for the output."""
    out = int(model.recommended_settings.get("max_tokens", DEFAULT_MAX_TOKENS))
    return math.ceil(len(prompt) / 2) + out


@dataclass
class Candidate:
    model_id: str
    priority: int
    rejected_reason: str | None = None


@dataclass
class Selection:
    model: ModelDefinition
    reason: str
    candidates: list[Candidate] = field(default_factory=list)


def select_model(
    config: ModelsConfig,
    required_capabilities: list[str],
    prompt: str = "",
    exclude: list[str] | None = None,
    loaded_model_id: str | None = None,
) -> Selection:
    exclude = exclude or []
    candidates: list[Candidate] = []
    eligible: list[ModelDefinition] = []
    for m in config.models:
        reason = None
        if not m.enabled:
            reason = "disabled"
        elif m.id in exclude:
            reason = "excluded"
        else:
            missing = [c for c in required_capabilities if c not in m.capabilities]
            if missing:
                reason = f"missing capabilities: {', '.join(missing)}"
            elif estimate_tokens(prompt, m) > m.max_context:
                reason = (
                    f"input too long: ~{estimate_tokens(prompt, m)} tokens "
                    f"> max_context {m.max_context}"
                )
            elif config.vram_limit_gb is not None and m.required_vram_gb > config.vram_limit_gb:
                reason = f"needs {m.required_vram_gb} GB VRAM > limit {config.vram_limit_gb} GB"
        candidates.append(Candidate(m.id, m.priority, reason))
        if reason is None:
            eligible.append(m)

    if not eligible:
        detail = "; ".join(f"{c.model_id}: {c.rejected_reason}" for c in candidates) or "no models"
        raise OrchestratorError(
            NO_CAPABLE_MODEL,
            f"no model satisfies {required_capabilities} ({detail})",
        )

    # priority desc; on ties prefer the model that is already loaded (saves a swap)
    eligible.sort(key=lambda m: (-m.priority, m.id != loaded_model_id, m.id))
    best = eligible[0]
    reason = f"priority {best.priority}"
    if best.id == loaded_model_id:
        reason += ", already loaded"
    return Selection(best, reason, candidates)
