import pytest

from diting import __main__ as mainmod


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
