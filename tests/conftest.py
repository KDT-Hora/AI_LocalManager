from __future__ import annotations

import textwrap

import pytest

from ai_orchestrator.settings import Settings
from ai_orchestrator.workflow.service import Orchestrator
from tests.fakes.fake_lmstudio import FakeLMStudio

MODELS_YAML = textwrap.dedent(
    """
    vram_limit_gb: 24
    models:
      - id: writer-a
        lmstudio_id: writer-a
        capabilities: [story, character_design]
        priority: 80
        max_context: 8000
        required_vram_gb: 10
        recommended_settings: { max_tokens: 500 }
      - id: writer-b
        lmstudio_id: writer-b
        capabilities: [story, character_design]
        priority: 50
        max_context: 8000
        required_vram_gb: 6
        recommended_settings: { max_tokens: 500 }
      - id: coder
        lmstudio_id: coder
        capabilities: [code]
        priority: 70
        max_context: 8000
        recommended_settings: { max_tokens: 500 }
    """
)


@pytest.fixture
def fake():
    server = FakeLMStudio().start()
    yield server
    server.stop()


@pytest.fixture
def models_path(tmp_path):
    p = tmp_path / "models.yaml"
    p.write_text(MODELS_YAML, encoding="utf-8")
    return p


@pytest.fixture
def settings(tmp_path, models_path, fake):
    return Settings(
        workspace=tmp_path / "workspace",
        models_path=models_path,
        lmstudio_url=fake.url,
        timeout=5,
        max_revisions=3,
        lms_bin=None,
    )


@pytest.fixture
def orch(settings):
    return Orchestrator(settings)
