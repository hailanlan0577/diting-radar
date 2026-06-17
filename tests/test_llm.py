import pytest
from diting.llm import DeepSeekClient

class _FakeResp:
    def __init__(self, content): self._c = content
    def raise_for_status(self): pass
    def json(self): return {"choices": [{"message": {"content": self._c}}]}

def test_complete_returns_text(monkeypatch):
    client = DeepSeekClient("http://x/v1", "k", "deepseek-v4-pro")
    monkeypatch.setattr(client._http, "post", lambda *a, **k: _FakeResp("hello"))
    assert client.complete([{"role": "user", "content": "hi"}]) == "hello"

def test_complete_json_parses(monkeypatch):
    client = DeepSeekClient("http://x/v1", "k", "deepseek-v4-pro")
    monkeypatch.setattr(client._http, "post", lambda *a, **k: _FakeResp('{"a": 1}'))
    assert client.complete_json([{"role": "user", "content": "hi"}]) == {"a": 1}

def test_complete_json_raises_on_bad_json(monkeypatch):
    client = DeepSeekClient("http://x/v1", "k", "deepseek-v4-pro")
    monkeypatch.setattr(client._http, "post", lambda *a, **k: _FakeResp("not-json"))
    with pytest.raises(ValueError, match="合法 JSON"):
        client.complete_json([{"role": "user", "content": "hi"}])
