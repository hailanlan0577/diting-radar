# src/diting/llm.py
from __future__ import annotations
import json
import httpx

class DeepSeekClient:
    def __init__(self, base_url: str, api_key: str, model: str, timeout: float = 120.0):
        self.model = model
        self._http = httpx.Client(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=timeout,
        )

    def complete(self, messages: list[dict], **kw) -> str:
        resp = self._http.post("/chat/completions",
                               json={"model": self.model, "messages": messages, **kw})
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]

    def complete_json(self, messages: list[dict], **kw) -> dict:
        kw.setdefault("response_format", {"type": "json_object"})
        text = self.complete(messages, **kw)
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"DeepSeek 没返回合法 JSON：{text[:200]}") from e
