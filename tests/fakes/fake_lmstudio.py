"""Minimal OpenAI-compatible fake of LM Studio for deterministic tests."""

from __future__ import annotations

import json
import threading
import time
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class FakeLMStudio:
    def __init__(self) -> None:
        # reply(model, prompt) -> text. Override per test.
        self.reply: Callable[[str, str], str] = lambda model, prompt: f"[{model}] OK"
        self.unknown_models: set[str] = set()  # -> 404 (model load failure)
        self.delay: float = 0.0  # seconds before replying (timeout tests)
        self.reasoning_only: bool = False  # reasoning model that ran out of tokens
        self.malformed: bool = False  # respond with a body that lacks `choices`
        self.calls: list[tuple[str, str]] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *a):  # silence
                pass

            def _send(self, code: int, body: dict) -> None:
                data = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                if self.path == "/v1/models":
                    self._send(200, {"data": []})
                else:
                    self._send(404, {"error": "not found"})

            def do_POST(self):
                length = int(self.headers.get("Content-Length", 0))
                body = json.loads(self.rfile.read(length) or b"{}")
                model = body.get("model", "")
                prompt = body["messages"][-1]["content"]
                if model in outer.unknown_models:
                    self._send(404, {"error": {"message": f"model '{model}' not found"}})
                    return
                if outer.delay:
                    time.sleep(outer.delay)
                outer.calls.append((model, prompt))
                if outer.malformed:
                    self._send(200, {"unexpected": True})
                    return
                if outer.reasoning_only:
                    msg = {"role": "assistant", "content": "", "reasoning_content": "thinking..."}
                    self._send(200, {"choices": [{"message": msg, "finish_reason": "length"}]})
                    return
                text = outer.reply(model, prompt)
                self._send(200, {"choices": [{"message": {"role": "assistant", "content": text}}]})

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)

    @property
    def url(self) -> str:
        host, port = self._server.server_address
        return f"http://{host}:{port}"

    def start(self) -> FakeLMStudio:
        self._thread.start()
        return self

    def stop(self) -> None:
        self._server.shutdown()
        self._server.server_close()
