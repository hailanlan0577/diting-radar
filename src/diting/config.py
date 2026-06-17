from __future__ import annotations
import os
from dataclasses import dataclass
import yaml

@dataclass(frozen=True)
class Config:
    deepseek_base_url: str
    deepseek_model: str
    deepseek_api_key_env: str
    session_records_dir: str
    lookback_days: int
    searxng_url: str
    github_token_env: str
    vault_inbox_dir: str
    feishu_target: str
    state_dir: str

    @property
    def deepseek_api_key(self) -> str:
        key = os.environ.get(self.deepseek_api_key_env)
        if not key:
            raise RuntimeError(f"环境变量 {self.deepseek_api_key_env} 未设置（DeepSeek API key）")
        return key

def load_config(path: str | None = None) -> Config:
    path = path or os.path.join(os.path.dirname(__file__), "..", "..", "config.yaml")
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return Config(
        deepseek_base_url=raw["deepseek"]["base_url"],
        deepseek_model=raw["deepseek"]["model"],
        deepseek_api_key_env=raw["deepseek"]["api_key_env"],
        session_records_dir=raw["signal"]["session_records_dir"],
        lookback_days=int(raw["signal"]["lookback_days"]),
        searxng_url=raw["crawl"]["searxng_url"],
        github_token_env=raw["crawl"]["github_token_env"],
        vault_inbox_dir=raw["deliver"]["vault_inbox_dir"],
        feishu_target=raw["deliver"]["feishu_target"],
        state_dir=raw["state_dir"],
    )
