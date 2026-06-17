import os, textwrap
import pytest
from diting.config import load_config

def test_load_config_reads_fields(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "deepseek-v4-pro", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.deepseek_base_url == "http://x/v1"
    assert cfg.deepseek_model == "deepseek-v4-pro"
    assert cfg.deepseek_api_key_env == "DS_KEY"
    assert cfg.session_records_dir == "/recs"
    assert cfg.lookback_days == 3
    assert cfg.searxng_url == "http://s:8080"
    assert cfg.github_token_env == "GH"
    assert cfg.vault_inbox_dir == "/inbox"
    assert cfg.feishu_target == "me"
    assert cfg.state_dir == "/st"

def test_api_key_missing_raises(tmp_path, monkeypatch):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text('deepseek: {base_url: "x", model: "m", api_key_env: "NOPE_KEY"}\n'
                        'signal: {session_records_dir: "/r", lookback_days: 1}\n'
                        'crawl: {searxng_url: "u", github_token_env: "G"}\n'
                        'deliver: {vault_inbox_dir: "/i", feishu_target: "me"}\nstate_dir: "/s"\n')
    monkeypatch.delenv("NOPE_KEY", raising=False)
    cfg = load_config(str(cfg_file))
    with pytest.raises(RuntimeError, match="NOPE_KEY"):
        _ = cfg.deepseek_api_key
