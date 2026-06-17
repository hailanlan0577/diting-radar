from diting.sources.github import search_github_repos

class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

def test_github_parses():
    payload = {"items": [{"full_name": "org/repo", "html_url": "http://gh/org/repo",
                          "description": "fast LoRA"}]}
    out = search_github_repos("lora", get=lambda *a, **k: _Resp(payload))
    assert out[0].title == "org/repo" and out[0].source == "github"
    assert "LoRA" in out[0].summary

def test_github_degrades():
    def boom(*a, **k): raise RuntimeError("403")
    assert search_github_repos("x", get=boom) == []
