import pytest

from ai_orchestrator.errors import OrchestratorError
from ai_orchestrator.models.model_definition import ModelsConfig
from ai_orchestrator.registry.selection import select_model


def cfg(*models, vram=None):
    return ModelsConfig.model_validate({"vram_limit_gb": vram, "models": list(models)})


def m(id, caps, priority=50, ctx=8000, vram=0, enabled=True, tokens=100):
    return {
        "id": id,
        "lmstudio_id": id,
        "capabilities": caps,
        "priority": priority,
        "max_context": ctx,
        "required_vram_gb": vram,
        "enabled": enabled,
        "recommended_settings": {"max_tokens": tokens},
    }


def test_capability_match_and_priority():
    c = cfg(m("a", ["story"], 50), m("b", ["story"], 90), m("c", ["code"], 99))
    assert select_model(c, ["story"]).model.id == "b"


def test_all_required_capabilities_needed():
    c = cfg(m("a", ["story"], 90), m("b", ["story", "worldbuilding"], 10))
    assert select_model(c, ["story", "worldbuilding"]).model.id == "b"


def test_tie_prefers_loaded_model():
    c = cfg(m("a", ["story"], 50), m("b", ["story"], 50))
    assert select_model(c, ["story"], loaded_model_id="b").model.id == "b"
    assert select_model(c, ["story"]).model.id == "a"


def test_disabled_and_excluded_skipped():
    c = cfg(m("a", ["story"], 90, enabled=False), m("b", ["story"], 80), m("c", ["story"], 10))
    assert select_model(c, ["story"], exclude=["b"]).model.id == "c"


def test_context_constraint():
    c = cfg(m("small", ["story"], 90, ctx=300), m("big", ["story"], 10, ctx=8000))
    sel = select_model(c, ["story"], prompt="x" * 1000)  # ~500 + 100 tokens
    assert sel.model.id == "big"
    assert (
        "input too long" in next(x for x in sel.candidates if x.model_id == "small").rejected_reason
    )


def test_vram_constraint():
    c = cfg(m("huge", ["story"], 90, vram=40), m("ok", ["story"], 10, vram=8), vram=24)
    assert select_model(c, ["story"]).model.id == "ok"


def test_no_capable_model():
    c = cfg(m("a", ["story"]))
    with pytest.raises(OrchestratorError) as e:
        select_model(c, ["nonexistent"])
    assert e.value.kind == "no_capable_model"
