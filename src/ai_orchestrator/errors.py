"""Typed errors returned to the orchestrating agent (contracts/mcp-tools.md)."""

from __future__ import annotations

NO_CAPABLE_MODEL = "no_capable_model"
MODEL_LOAD_FAILED = "model_load_failed"
BACKEND_UNREACHABLE = "backend_unreachable"
TIMEOUT = "timeout"
INVALID_OUTPUT = "invalid_output"
INVALID_TRANSITION = "invalid_transition"
REVISION_LIMIT_REACHED = "revision_limit_reached"
NOT_FOUND = "not_found"
UNSUPPORTED_BACKEND = "unsupported_backend"
CORRUPTED_DATA = "corrupted_data"


class OrchestratorError(Exception):
    def __init__(self, kind: str, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.retryable = retryable

    def to_dict(self) -> dict:
        return {"kind": self.kind, "message": self.message, "retryable": self.retryable}
