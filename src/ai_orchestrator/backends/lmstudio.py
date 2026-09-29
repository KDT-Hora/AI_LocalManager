"""LM Studio backend.

API findings (T006, verified against the installed `lms` CLI, 2026-09-29):
- Generation: OpenAI-compatible REST `POST {base}/v1/chat/completions` with
  `model` = LM Studio model key. With JIT loading enabled, LM Studio loads the model
  on first request, so `launch.method: jit` needs no explicit load.
- Explicit load/unload: `lms load <key> --identifier <key> -y`, `lms unload <identifier>`,
  `lms ps --json` (loaded models). Used for `launch.method: lms_cli`.
- The local server must be running (`lms server start`); otherwise connections are refused
  and we report `backend_unreachable`.
"""

from __future__ import annotations

import asyncio
import json

import httpx

from ..errors import (
    BACKEND_UNREACHABLE,
    INVALID_OUTPUT,
    MODEL_LOAD_FAILED,
    TIMEOUT,
    OrchestratorError,
)
from ..logging_setup import get_logger
from ..models.model_definition import ModelDefinition
from ..settings import Settings
from .base import ensure_supported


class LMStudioBackend:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    # ---- lms CLI -------------------------------------------------------
    async def _lms(self, *args: str, timeout: float | None = None) -> str:
        if not self.settings.lms_bin:
            raise OrchestratorError(
                MODEL_LOAD_FAILED, "`lms` CLI not found (set AIO_LMS_BIN or use launch.method=jit)"
            )
        try:
            proc = await asyncio.create_subprocess_exec(
                self.settings.lms_bin,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            out, err = await asyncio.wait_for(
                proc.communicate(), timeout or self.settings.load_timeout
            )
        except TimeoutError as e:
            raise OrchestratorError(
                TIMEOUT, f"lms {' '.join(args)} timed out", retryable=True
            ) from e
        except OSError as e:
            raise OrchestratorError(MODEL_LOAD_FAILED, f"cannot run lms: {e}") from e
        if proc.returncode != 0:
            raise OrchestratorError(
                MODEL_LOAD_FAILED,
                f"lms {' '.join(args)} failed: {err.decode(errors='replace').strip()}",
                retryable=True,
            )
        return out.decode(errors="replace")

    async def loaded_identifiers(self) -> set[str]:
        out = await self._lms("ps", "--json", timeout=30)
        try:
            data = json.loads(out or "[]")
        except json.JSONDecodeError:
            return set()
        return {str(d.get("identifier") or d.get("modelKey")) for d in data}

    # ---- Backend API ---------------------------------------------------
    async def prepare(
        self,
        model: ModelDefinition,
        previous: ModelDefinition | None = None,
        vram_limit_gb: float | None = None,
    ) -> None:
        ensure_supported(model)
        if (
            previous is not None
            and previous.id != model.id
            and previous.launch.method == "lms_cli"
            and vram_limit_gb is not None
            and previous.required_vram_gb + model.required_vram_gb > vram_limit_gb
        ):
            await self._lms("unload", previous.lmstudio_id, timeout=60)
        if model.launch.method == "lms_cli":
            if model.lmstudio_id not in await self.loaded_identifiers():
                args = ["load", model.lmstudio_id, "--identifier", model.lmstudio_id, "-y"]
                if model.launch.context_length:
                    args += ["-c", str(model.launch.context_length)]
                await self._lms(*args)

    async def chat(self, model: ModelDefinition, prompt: str) -> str:
        ensure_supported(model)
        settings = model.recommended_settings
        body: dict = {
            "model": model.lmstudio_id,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }
        for key in ("temperature", "top_p", "max_tokens"):
            if key in settings:
                body[key] = settings[key]
        url = self.settings.lmstudio_url.rstrip("/") + "/v1/chat/completions"
        try:
            async with httpx.AsyncClient(timeout=self.settings.timeout) as client:
                resp = await client.post(url, json=body)
        except (httpx.ConnectError, httpx.ConnectTimeout) as e:
            raise OrchestratorError(
                BACKEND_UNREACHABLE,
                f"cannot connect to LM Studio at {self.settings.lmstudio_url} "
                "(is the server running? `lms server start`)",
                retryable=True,
            ) from e
        except httpx.TimeoutException as e:
            raise OrchestratorError(
                TIMEOUT,
                f"generation exceeded {self.settings.timeout}s for '{model.id}'",
                retryable=True,
            ) from e
        except httpx.HTTPError as e:
            raise OrchestratorError(BACKEND_UNREACHABLE, f"HTTP error: {e}", retryable=True) from e

        if resp.status_code in (400, 404):
            raise OrchestratorError(
                MODEL_LOAD_FAILED,
                f"LM Studio rejected model '{model.lmstudio_id}': {resp.text[:300]}",
            )
        if resp.status_code >= 400:
            raise OrchestratorError(
                BACKEND_UNREACHABLE,
                f"LM Studio returned {resp.status_code}: {resp.text[:300]}",
                retryable=True,
            )
        try:
            choice = resp.json()["choices"][0]
            content = choice["message"].get("content") or ""
            reasoning = choice["message"].get("reasoning_content") or ""
            finish = choice.get("finish_reason")
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as e:
            raise OrchestratorError(
                INVALID_OUTPUT, f"unexpected response shape from LM Studio: {e}"
            ) from e
        if not content.strip() and reasoning:
            # Reasoning models can spend the whole token budget thinking (observed with Qwen3.x).
            hint = " — raise recommended_settings.max_tokens" if finish == "length" else ""
            raise OrchestratorError(
                INVALID_OUTPUT,
                f"model '{model.id}' produced only reasoning and no answer "
                f"(finish_reason={finish}){hint}",
                retryable=True,
            )
        if finish == "length":
            get_logger().warning("'%s' hit max_tokens; the output may be truncated", model.id)
        return content
