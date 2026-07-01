import pytest

from diting import __main__ as mainmod
from diting.models import Candidate, DigReport


def test_main_routes_ask_command(monkeypatch, capsys):
    class _Cfg:
        pass

    class _Client:
        pass

    monkeypatch.setattr(mainmod, "load_config", lambda: _Cfg())
    monkeypatch.setattr(mainmod, "_client", lambda cfg: _Client())
    monkeypatch.setattr(mainmod, "_run_ask", lambda cfg, client, topic, mode, max_sources: f"{topic}|{mode}|{max_sources}")
    monkeypatch.setattr("sys.argv", ["diting", "ask", "OpenAI Agents SDK", "--mode", "brief", "--max-sources", "7"])

    mainmod.main()

    assert capsys.readouterr().out.strip() == "OpenAI Agents SDK|brief|7"


def test_main_ask_reports_config_error(monkeypatch):
    monkeypatch.setattr(mainmod, "load_config", lambda: (_ for _ in ()).throw(RuntimeError("missing key")))
    monkeypatch.setattr("sys.argv", ["diting", "ask", "OpenAI Agents SDK"])

    with pytest.raises(SystemExit, match="配置/密钥错误：missing key"):
        mainmod.main()


def test_run_ask_dig_prefers_search_web(monkeypatch):
    class _Cfg:
        known_antibot_domains = ()
        searxng_url = "http://sx:8080"

    calls = {}

    monkeypatch.setattr("diting.dig.generate_dig_queries", lambda client, topic: ["q1"])
    monkeypatch.setattr(
        "diting.sources.websearch.search_web",
        lambda q, searxng_url, max_results=5: calls.setdefault("searches", []).append((q, searxng_url, max_results)) or [Candidate("T", "http://u", "摘要", "websearch")],
    )
    monkeypatch.setattr("diting.sources.fetch.search_engine", lambda *a, **k: (_ for _ in ()).throw(AssertionError("dig ask 不该先走 DDG 兜底")))
    monkeypatch.setattr("diting.crawl.enrich_bodies", lambda cands, top_n, antibot_domains: cands)
    monkeypatch.setattr("diting.dig.synthesize_dig", lambda client, topic, date, cands: DigReport(topic, date, "## 概览\n正文", "一句话", len(cands)))

    out = mainmod._run_ask(_Cfg(), object(), "OpenAI Agents SDK", "dig", 3)

    assert out == "一句话\n\n## 概览\n正文"
    assert calls["searches"] == [("q1", "http://sx:8080", 3)]
