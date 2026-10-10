"""OpenAI-compatible chat client for the local Apertus server (llama.cpp)."""
from __future__ import annotations

import json
import time

import httpx

from beneficia import config


class ModelUnavailable(RuntimeError):
    pass


class LLMClient:
    def __init__(self, base_url: str | None = None, model: str | None = None, api_key: str | None = None,
                 timeout: float = 900.0):
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.model = model or config.LLM_NAME
        self.api_key = api_key or config.LLM_API_KEY
        self.timeout = timeout
        self.calls: list[dict] = []  # timings per call, for the report

    def health(self) -> bool:
        root = self.base_url[:-3] if self.base_url.endswith("/v1") else self.base_url
        try:
            r = httpx.get(root + "/health", timeout=5)
            return r.status_code == 200
        except httpx.HTTPError:
            return False

    def complete_json(self, system: str, user: str, schema: dict, max_tokens: int = 600,
                      example: tuple[str, str] | None = None) -> dict:
        messages = [{"role": "system", "content": system}]
        if example:
            messages += [{"role": "user", "content": example[0]}, {"role": "assistant", "content": example[1]}]
        messages.append({"role": "user", "content": user})
        body = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": "rows", "schema": schema}},
        }
        t0 = time.time()
        try:
            r = httpx.post(self.base_url + "/chat/completions", json=body, timeout=self.timeout,
                           headers={"Authorization": f"Bearer {self.api_key}"})
            r.raise_for_status()
        except httpx.HTTPError as exc:
            raise ModelUnavailable(str(exc)) from exc
        data = r.json()
        content = data["choices"][0]["message"]["content"]
        t = data.get("timings", {})
        self.calls.append({"seconds": round(time.time() - t0, 2), "prompt_tokens": t.get("prompt_n"),
                           "completion_tokens": t.get("predicted_n"),
                           "finish": data["choices"][0].get("finish_reason")})
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            return {}


class ReplayClient:
    """Replays recorded model outputs in call order (integration tests, fast iteration on code)."""

    def __init__(self, model_responses: list[dict], model: str = "replay"):
        self.queue = [m["output"] for m in model_responses]
        self.model = model
        self.calls: list[dict] = []

    def health(self) -> bool:
        return True

    def complete_json(self, system, user, schema, max_tokens=600, example=None) -> dict:
        self.calls.append({"seconds": 0.0})
        return self.queue.pop(0) if self.queue else {}
