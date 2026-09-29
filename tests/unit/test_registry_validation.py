import pytest

from ai_orchestrator.registry.loader import RegistryError, load_config


def write(tmp_path, text):
    p = tmp_path / "m.yaml"
    p.write_text(text, encoding="utf-8")
    return p


BASE = "  - id: {id}\n    lmstudio_id: x\n    capabilities: {caps}\n    priority: {pr}\n    max_context: 100\n"


def test_valid(tmp_path):
    p = write(tmp_path, "models:\n" + BASE.format(id="a", caps="[story]", pr=10))
    assert load_config(p).models[0].id == "a"


def test_duplicate_id(tmp_path):
    body = BASE.format(id="a", caps="[story]", pr=1) + BASE.format(id="a", caps="[code]", pr=2)
    with pytest.raises(RegistryError, match="duplicate"):
        load_config(write(tmp_path, "models:\n" + body))


def test_empty_capabilities(tmp_path):
    with pytest.raises(RegistryError, match="capabilities"):
        load_config(write(tmp_path, "models:\n" + BASE.format(id="a", caps="[]", pr=1)))


def test_priority_out_of_range(tmp_path):
    with pytest.raises(RegistryError, match="priority"):
        load_config(write(tmp_path, "models:\n" + BASE.format(id="a", caps="[x]", pr=101)))


def test_missing_file(tmp_path):
    with pytest.raises(RegistryError, match="not found"):
        load_config(tmp_path / "nope.yaml")


def test_shipped_models_yaml_is_valid():
    from pathlib import Path

    assert load_config(Path("config/models.yaml")).models
