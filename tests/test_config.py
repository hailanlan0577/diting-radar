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

def test_fetch_fields_default_when_absent(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.fetch_top_n == 5
    assert cfg.known_antibot_domains == ("zhihu.com", "csdn.net")

def test_fetch_fields_read_from_crawl(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH", fetch_top_n: 8, known_antibot_domains: ["weixin.qq.com"]}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.fetch_top_n == 8
    assert cfg.known_antibot_domains == ("weixin.qq.com",)

def test_dig_fields_default_when_absent(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.dig_max_sources == 12
    assert cfg.dig_vault_dir == "/inbox"
    assert cfg.dig_queue_path == "/st/dig_queue.yaml"

def test_dig_fields_read_from_yaml(tmp_path):
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me", dig_vault_dir: "/vault/谛听深挖", dig_max_sources: 8}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.dig_vault_dir == "/vault/谛听深挖"
    assert cfg.dig_max_sources == 8

def test_project_radar_defaults_when_absent(tmp_path):
    import textwrap
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.project_radar_status_dir == ""
    assert cfg.project_radar_output_dir == ""
    assert cfg.project_radar_projects == ()


def test_project_radar_read_from_yaml(tmp_path):
    import textwrap
    from diting.config import ProjectSpec
    cfg_file = tmp_path / "config.yaml"
    cfg_file.write_text(textwrap.dedent("""
        deepseek: {base_url: "http://x/v1", model: "m", api_key_env: "DS_KEY"}
        signal: {session_records_dir: "/recs", lookback_days: 3}
        crawl: {searxng_url: "http://s:8080", github_token_env: "GH"}
        deliver: {vault_inbox_dir: "/inbox", feishu_target: "me"}
        state_dir: "/st"
        project_radar:
          status_dir: "/Users/<run-user>/project-status"
          output_dir: "/vault/谛听项目情报"
          projects:
            - {slug: "ytst", match: "ytst"}
            - {slug: "lbc", match: "luxury-bag-copilot"}
    """))
    cfg = load_config(str(cfg_file))
    assert cfg.project_radar_status_dir == "/Users/<run-user>/project-status"
    assert cfg.project_radar_output_dir == "/vault/谛听项目情报"
    assert cfg.project_radar_projects == (
        ProjectSpec(slug="ytst", match="ytst"),
        ProjectSpec(slug="lbc", match="luxury-bag-copilot"),
    )
