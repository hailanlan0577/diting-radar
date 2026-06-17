# 谛听（Dìtīng）v1 实现计划 — 引擎 + 科研雷达端到端

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打通"读你最近的脑力劳动记录 → DeepSeek V4 Pro 蒸出兴趣 → 全网爬 → 砍掉已知 → 合成带'为何重要'的情报 → 发飞书+Obsidian"整条流水线，先在 🔭 科研雷达 这一个镜头上跑通、可手动触发。

**Architecture:** 单进程 Python 流水线，6 段（signal → query → crawl → novelty → synthesize → deliver）。每段是一个聚焦的小模块，靠 dataclass 定义的不可变数据对象在段间传递。所有 LLM 判断走 DeepSeek V4 Pro（OpenAI 兼容 API）；外部 I/O（LLM、网络、lark-cli）在测试里全部 mock，业务逻辑纯函数化便于测试。

**Tech Stack:** Python 3.11+、httpx（HTTP）、pyyaml（配置/画像）、sqlite3（stdlib，跨天去重）、trafilatura（正文抽取）、pytest（测试）、lark-cli（飞书投递，subprocess 调用）、DeepSeek V4 Pro（复用 OpenClaw 的 `deepseek-v4-pro`，OpenAI 兼容）。

## Global Constraints

> 每个 Task 的要求都隐含包含本节，逐条来自 spec。

- **Python 3.11+**（用到 `tomllib`、`X | None` 语法）。
- **全程 DeepSeek V4 Pro**：所有 LLM 调用走同一个客户端，**不引入任何本地模型推理**。
- **不碰 Mac Studio 8088 / 本地模型**：本项目只做调度 + 调云端 API。
- **precision-first（宁缺毋滥）**：合成层若无够格新东西，输出"今天这块没值得看的"，**绝不硬凑**。
- **不可变数据**：段间传递的对象用 `@dataclass(frozen=True)`，转换返回新对象，不就地改。
- **小文件**：单文件 <400 行，按职责拆分，会变的放一起。
- **错误显式**：任一信号源/爬源失败 → 跳过该源 + 在结果里记一条"X 源没取到"，**绝不静默吞掉**。
- **外部输入不可信**：API 返回、网页正文先做基本校验再喂给 LLM。
- **配置不进 git**：`config.yaml`、`state/` 全部 gitignore；只提交 `config.example.yaml`。

---

## File Structure

```
~/diting-radar/
  pyproject.toml              # 依赖 + 包配置
  .gitignore
  config.example.yaml         # 配置模板（提交）
  config.yaml                 # 真实配置（gitignore）
  src/diting/
    __init__.py
    __main__.py               # CLI 入口：python -m diting ...
    config.py                 # 加载 config.yaml + 环境变量
    models.py                 # frozen dataclass：InterestProfile/SignalItem/Interests/Candidate/RankedItem/Report
    state.py                  # StateStore：pushed.db(SQLite) + interest_profile.yaml + runs/
    llm.py                    # DeepSeekClient：complete() / complete_json()
    signal/
      __init__.py
      obsidian.py             # 读最近的 Obsidian 会话记录 .md
      distill.py              # DeepSeek：原文 → Interests(兴趣画像)
      profile.py              # 关注清单：load + seed 生成
    query.py                  # 镜头 → 查询串（科研镜头）
    sources/
      __init__.py
      arxiv.py                # arXiv API
      hackernews.py           # HN Algolia API
      github.py               # GitHub repo 搜索
      websearch.py            # searxng 搜 + trafilatura 抽正文
    crawl.py                  # 编排：跑 queries × sources → 候选，按 URL 去重
    novelty.py                # 跨天去重 + DeepSeek 新颖度判定
    synthesize.py             # DeepSeek：候选 → RankedItem（带"为何重要"，空诚实）
    deliver/
      __init__.py
      obsidian_out.py         # 追加到 vault Inbox/ 当天笔记
      feishu.py               # lark-cli 发飞书
    runner.py                 # 镜头 → 全流水线 → 投递
  tests/                      # 镜像 src 结构
  state/                      # gitignore：pushed.db / interest_profile.yaml / runs/
```

每个 Task 产出独立可测的交付物。外部 I/O 全部可 mock。

---

### Task 1: 项目骨架 + 配置加载

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `config.example.yaml`
- Create: `src/diting/__init__.py`, `src/diting/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `diting.config.load_config(path: str | None = None) -> Config`，`Config` 是 frozen dataclass，字段见下。`Config.deepseek_api_key -> str`（从环境变量读，缺失抛 `RuntimeError`）。

- [ ] **Step 1: 写 pyproject.toml 与依赖**

```toml
# pyproject.toml
[project]
name = "diting"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = ["httpx>=0.27", "pyyaml>=6.0", "trafilatura>=1.12"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[tool.setuptools.packages.find]
where = ["src"]
```

- [ ] **Step 2: 写 .gitignore 和 config.example.yaml**

```gitignore
# .gitignore
__pycache__/
*.pyc
.pytest_cache/
.venv/
config.yaml
state/
```

```yaml
# config.example.yaml — 拷成 config.yaml 后填真实值
deepseek:
  base_url: "https://api.deepseek.com/v1"   # ✅ 已核对：Mac Studio OpenClaw 的 deepseek provider
  model: "deepseek-v4-pro"                   # provider 里有 deepseek-v4-flash / -pro 两个，取 pro
  api_key_env: "DEEPSEEK_API_KEY"           # 真实 key 放环境变量；值=macstudio ~/.openclaw/openclaw.json providers.deepseek.apiKey
signal:
  session_records_dir: "/Users/<dev-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/会话记录"
  lookback_days: 5
crawl:
  searxng_url: "http://localhost:8080"      # ✅ 已核对：本机 searxng 实例
  github_token_env: "GITHUB_TOKEN"
deliver:
  vault_inbox_dir: "/Users/<dev-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/Inbox"
  feishu_target: "ou_你的openid"             # 飞书 open_id(ou_开头)，发私聊；获取方式见"手动验收"
state_dir: "/Users/<dev-user>/diting-radar/state"
```

- [ ] **Step 3: 写失败测试 `tests/test_config.py`**

```python
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
    assert cfg.deepseek_model == "deepseek-v4-pro"
    assert cfg.lookback_days == 3
    assert cfg.searxng_url == "http://s:8080"

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
```

- [ ] **Step 4: 运行测试，确认失败**

Run: `cd ~/diting-radar && pip install -e ".[dev]" && pytest tests/test_config.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.config`）

- [ ] **Step 5: 写 `src/diting/__init__.py`（空）和 `src/diting/config.py`**

```python
# src/diting/config.py
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
```

- [ ] **Step 6: 运行测试，确认通过**

Run: `pytest tests/test_config.py -v`
Expected: PASS（2 passed）

- [ ] **Step 7: 提交**

```bash
git add pyproject.toml .gitignore config.example.yaml src/diting/__init__.py src/diting/config.py tests/test_config.py
git commit -m "feat: 项目骨架 + 配置加载"
```

---

### Task 2: 数据模型 + 状态存储

**Files:**
- Create: `src/diting/models.py`, `src/diting/state.py`
- Test: `tests/test_models.py`, `tests/test_state.py`

**Interfaces:**
- Produces（后续所有 Task 都依赖这些类型）：
  - `SignalItem(source: str, text: str, mtime: float)` — 一条原始信号。
  - `Interests(topics: tuple[str,...], entities: tuple[str,...], open_loops: tuple[str,...], decisions: tuple[str,...])` — 兴趣画像。
  - `Candidate(title: str, url: str, summary: str, source: str)` — 爬回的候选。
  - `RankedItem(title: str, url: str, one_liner: str, why_it_matters: str, source: str, lens: str)` — 合成后的成品条目。
  - `Report(lens: str, date: str, items: tuple[RankedItem,...], notes: tuple[str,...])` — 一份报告；`items` 为空 + `notes` 说明即"今天没值得看的"。
  - `StateStore(state_dir: str)`，方法：`is_pushed(url) -> bool`、`mark_pushed(url, title)`、`load_profile() -> dict`、`save_profile(dict)`。

- [ ] **Step 1: 写失败测试 `tests/test_models.py`**

```python
from diting.models import Interests, RankedItem, Report

def test_interests_is_frozen():
    i = Interests(topics=("LoRA",), entities=("MLX",), open_loops=(), decisions=())
    import dataclasses, pytest
    with pytest.raises(dataclasses.FrozenInstanceError):
        i.topics = ()

def test_empty_report_is_honest():
    r = Report(lens="research", date="2026-06-18", items=(), notes=("今天这块没值得看的",))
    assert r.is_empty() is True
    assert "没值得看" in r.notes[0]
```

- [ ] **Step 2: 运行，确认失败**

Run: `pytest tests/test_models.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.models`）

- [ ] **Step 3: 写 `src/diting/models.py`**

```python
# src/diting/models.py
from __future__ import annotations
from dataclasses import dataclass

@dataclass(frozen=True)
class SignalItem:
    source: str
    text: str
    mtime: float

@dataclass(frozen=True)
class Interests:
    topics: tuple[str, ...]
    entities: tuple[str, ...]
    open_loops: tuple[str, ...]
    decisions: tuple[str, ...]

@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    summary: str
    source: str

@dataclass(frozen=True)
class RankedItem:
    title: str
    url: str
    one_liner: str
    why_it_matters: str
    source: str
    lens: str

@dataclass(frozen=True)
class Report:
    lens: str
    date: str
    items: tuple[RankedItem, ...]
    notes: tuple[str, ...]

    def is_empty(self) -> bool:
        return len(self.items) == 0
```

- [ ] **Step 4: 运行，确认通过**

Run: `pytest tests/test_models.py -v`
Expected: PASS

- [ ] **Step 5: 写失败测试 `tests/test_state.py`**

```python
from diting.state import StateStore

def test_pushed_dedup(tmp_path):
    s = StateStore(str(tmp_path))
    assert s.is_pushed("http://a") is False
    s.mark_pushed("http://a", "标题A")
    assert s.is_pushed("http://a") is True
    assert s.is_pushed("http://b") is False

def test_profile_roundtrip(tmp_path):
    s = StateStore(str(tmp_path))
    assert s.load_profile() == {"stack": [], "tools": [], "topics": []}
    s.save_profile({"stack": ["MLX"], "tools": ["graphify"], "topics": ["LoRA"]})
    assert s.load_profile()["stack"] == ["MLX"]
```

- [ ] **Step 6: 运行，确认失败**

Run: `pytest tests/test_state.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.state`）

- [ ] **Step 7: 写 `src/diting/state.py`**

```python
# src/diting/state.py
from __future__ import annotations
import os, sqlite3
import yaml

_DEFAULT_PROFILE = {"stack": [], "tools": [], "topics": []}

class StateStore:
    def __init__(self, state_dir: str):
        self.dir = state_dir
        os.makedirs(self.dir, exist_ok=True)
        self._db = os.path.join(self.dir, "pushed.db")
        self._profile = os.path.join(self.dir, "interest_profile.yaml")
        with sqlite3.connect(self._db) as c:
            c.execute("CREATE TABLE IF NOT EXISTS pushed (url TEXT PRIMARY KEY, title TEXT)")

    def is_pushed(self, url: str) -> bool:
        with sqlite3.connect(self._db) as c:
            return c.execute("SELECT 1 FROM pushed WHERE url=?", (url,)).fetchone() is not None

    def mark_pushed(self, url: str, title: str) -> None:
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR IGNORE INTO pushed (url, title) VALUES (?, ?)", (url, title))

    def load_profile(self) -> dict:
        if not os.path.exists(self._profile):
            return dict(_DEFAULT_PROFILE)
        with open(self._profile, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or dict(_DEFAULT_PROFILE)

    def save_profile(self, profile: dict) -> None:
        with open(self._profile, "w", encoding="utf-8") as f:
            yaml.safe_dump(profile, f, allow_unicode=True)
```

- [ ] **Step 8: 运行，确认通过**

Run: `pytest tests/test_state.py -v`
Expected: PASS（4 passed 累计）

- [ ] **Step 9: 提交**

```bash
git add src/diting/models.py src/diting/state.py tests/test_models.py tests/test_state.py
git commit -m "feat: 数据模型 + 状态存储（去重库 + 关注清单）"
```

---

### Task 3: DeepSeek V4 Pro 客户端

**Files:** Create `src/diting/llm.py` · Test `tests/test_llm.py`

**Interfaces:**
- Produces: `DeepSeekClient(base_url, api_key, model)`，方法 `complete(messages: list[dict]) -> str` 和 `complete_json(messages: list[dict]) -> dict`（强制 JSON、解析失败抛 `ValueError`）。后续所有 LLM 调用都注入这个 client，测试里 mock 它，不打真网络。

- [ ] **Step 1: 写失败测试 `tests/test_llm.py`**（mock httpx，不打真网）

```python
import json
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
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_llm.py -v` → FAIL（无 `diting.llm`）

- [ ] **Step 3: 写 `src/diting/llm.py`**

```python
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
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_llm.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/llm.py tests/test_llm.py && git commit -m "feat: DeepSeek V4 Pro 客户端"`

---

### Task 4: Obsidian 会话记录采集器

**Files:** Create `src/diting/signal/__init__.py`, `src/diting/signal/obsidian.py` · Test `tests/test_obsidian.py`

**Interfaces:**
- Produces: `collect_session_records(records_dir: str, lookback_days: int, now_ts: float) -> list[SignalItem]` — 返回近 `lookback_days` 天内修改过的 `.md` 文件内容（按 mtime 倒序）。传 `now_ts` 进来是为了可测、不依赖真实时间。目录不存在时返回 `[]` 并不报错（降级）。

- [ ] **Step 1: 写失败测试 `tests/test_obsidian.py`**

```python
import os
from diting.signal.obsidian import collect_session_records

def test_collects_recent_md_only(tmp_path):
    recent = tmp_path / "今天.md"; recent.write_text("搞了 LoRA 微调", encoding="utf-8")
    old = tmp_path / "上月.md"; old.write_text("旧的", encoding="utf-8")
    now = 1_000_000.0
    os.utime(recent, (now, now))
    os.utime(old, (now - 40 * 86400, now - 40 * 86400))
    items = collect_session_records(str(tmp_path), lookback_days=5, now_ts=now)
    assert len(items) == 1
    assert "LoRA" in items[0].text
    assert items[0].source == "obsidian_session"

def test_missing_dir_degrades(tmp_path):
    assert collect_session_records(str(tmp_path / "nope"), 5, 1_000_000.0) == []
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_obsidian.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/signal/__init__.py`（空）和 `src/diting/signal/obsidian.py`**

```python
# src/diting/signal/obsidian.py
from __future__ import annotations
import os
from diting.models import SignalItem

def collect_session_records(records_dir: str, lookback_days: int, now_ts: float) -> list[SignalItem]:
    if not os.path.isdir(records_dir):
        return []
    cutoff = now_ts - lookback_days * 86400
    items: list[SignalItem] = []
    for name in os.listdir(records_dir):
        if not name.endswith(".md"):
            continue
        path = os.path.join(records_dir, name)
        try:
            mtime = os.path.getmtime(path)
            if mtime < cutoff:
                continue
            text = open(path, "r", encoding="utf-8").read()
        except OSError:
            continue
        items.append(SignalItem(source="obsidian_session", text=text, mtime=mtime))
    items.sort(key=lambda i: i.mtime, reverse=True)
    return items
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_obsidian.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/signal tests/test_obsidian.py && git commit -m "feat: Obsidian 会话记录采集器"`

---

### Task 5: 信号蒸馏器（原文 → 兴趣画像）

**Files:** Create `src/diting/signal/distill.py` · Test `tests/test_distill.py`

**Interfaces:**
- Consumes: `DeepSeekClient.complete_json`、`list[SignalItem]`。
- Produces: `distill_interests(client, items: list[SignalItem], max_chars: int = 24000) -> Interests` — 把原文拼接（截断到 `max_chars` 防超长）后让 DeepSeek 抽成兴趣画像。

- [ ] **Step 1: 写失败测试 `tests/test_distill.py`**（mock client）

```python
from diting.models import SignalItem, Interests
from diting.signal.distill import distill_interests

class _FakeClient:
    def __init__(self, payload): self.payload = payload; self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return self.payload

def test_distill_maps_to_interests():
    client = _FakeClient({"topics": ["LoRA 微调"], "entities": ["MLX", "ytst"],
                          "open_loops": ["阈值还没定"], "decisions": ["阈值改 0.3"]})
    out = distill_interests(client, [SignalItem("obsidian_session", "今天搞 LoRA", 1.0)])
    assert isinstance(out, Interests)
    assert out.topics == ("LoRA 微调",)
    assert "MLX" in out.entities
    # 确认把原文喂进了 prompt
    assert "今天搞 LoRA" in client.seen[-1]["content"]

def test_distill_tolerates_missing_keys():
    client = _FakeClient({"topics": ["x"]})
    out = distill_interests(client, [SignalItem("s", "t", 1.0)])
    assert out.entities == () and out.open_loops == ()
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_distill.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/signal/distill.py`**

```python
# src/diting/signal/distill.py
from __future__ import annotations
from diting.models import SignalItem, Interests

_SYSTEM = (
    "你是一个帮用户提炼'最近在钻研什么'的助手。读用户最近的工作/会话记录，"
    "抽出他正在追的技术话题、用到的工具/项目实体、悬而未决的问题（TODO/卡点）、当天做出的决策。"
    "只保留技术相关的，忽略生活琐事。严格输出 JSON："
    '{"topics": [..], "entities": [..], "open_loops": [..], "decisions": [..]}'
)

def distill_interests(client, items: list[SignalItem], max_chars: int = 24000) -> Interests:
    corpus = "\n\n---\n\n".join(i.text for i in items)[:max_chars]
    data = client.complete_json([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"以下是我最近的记录：\n\n{corpus}"},
    ])
    def tup(key): return tuple(data.get(key, []) or [])
    return Interests(topics=tup("topics"), entities=tup("entities"),
                     open_loops=tup("open_loops"), decisions=tup("decisions"))
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_distill.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/signal/distill.py tests/test_distill.py && git commit -m "feat: 信号蒸馏器（原文→兴趣画像）"`

---

### Task 6: 关注清单（seed 生成 + 自动喂胖）

**Files:** Create `src/diting/signal/profile.py` · Test `tests/test_profile.py`

**Interfaces:**
- Produces:
  - `seed_profile(client, source_texts: list[str]) -> dict` — 让 DeepSeek 从静态肥料（CLAUDE.md / 救命手册 / 底座手册原文）抽出 `{"stack": [..], "tools": [..], "topics": [..]}`。
  - `fatten_profile(profile: dict, interests: Interests) -> dict` — 纯函数，把今日兴趣里反复出现的实体/话题并进清单，返回**新 dict**（不改原对象，去重保序）。

- [ ] **Step 1: 写失败测试 `tests/test_profile.py`**

```python
from diting.models import Interests
from diting.signal.profile import seed_profile, fatten_profile

class _FakeClient:
    def complete_json(self, messages, **kw):
        return {"stack": ["MLX", "llama.cpp"], "tools": ["graphify"], "topics": ["细粒度检索"]}

def test_seed_profile_from_texts():
    p = seed_profile(_FakeClient(), ["我常用 MLX 和 graphify"])
    assert "MLX" in p["stack"] and "graphify" in p["tools"]

def test_fatten_is_pure_and_dedup():
    base = {"stack": ["MLX"], "tools": ["graphify"], "topics": ["LoRA"]}
    interests = Interests(topics=("LoRA", "RRF 融合"), entities=("MLX", "Qdrant"),
                          open_loops=(), decisions=())
    out = fatten_profile(base, interests)
    assert out["topics"] == ["LoRA", "RRF 融合"]      # 去重 + 新增
    assert "Qdrant" in out["tools"]                    # 新实体并入 tools
    assert base["topics"] == ["LoRA"]                  # 原对象未被改（不可变）
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_profile.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/signal/profile.py`**

```python
# src/diting/signal/profile.py
from __future__ import annotations
from diting.models import Interests

_SEED_SYSTEM = (
    "从用户的配置/手册文本里，抽出他长期依赖的技术栈、工具/skill、长期关注的技术话题。"
    "严格输出 JSON：{\"stack\": [..], \"tools\": [..], \"topics\": [..]}"
)

def seed_profile(client, source_texts: list[str]) -> dict:
    corpus = "\n\n---\n\n".join(source_texts)[:24000]
    data = client.complete_json([
        {"role": "system", "content": _SEED_SYSTEM},
        {"role": "user", "content": corpus},
    ])
    return {"stack": list(data.get("stack", []) or []),
            "tools": list(data.get("tools", []) or []),
            "topics": list(data.get("topics", []) or [])}

def _merge(existing: list[str], extra) -> list[str]:
    out = list(existing)
    for x in extra:
        if x not in out:
            out.append(x)
    return out

def fatten_profile(profile: dict, interests: Interests) -> dict:
    return {
        "stack": _merge(profile.get("stack", []), []),
        "tools": _merge(profile.get("tools", []), interests.entities),
        "topics": _merge(profile.get("topics", []), interests.topics),
    }
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_profile.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/signal/profile.py tests/test_profile.py && git commit -m "feat: 关注清单 seed 生成 + 自动喂胖"`

---

### Task 7: 查询生成器（科研镜头）

**Files:** Create `src/diting/query.py` · Test `tests/test_query.py`

**Interfaces:**
- Consumes: `DeepSeekClient`、`Interests`、`profile: dict`。
- Produces: `generate_queries(client, lens: str, interests: Interests, profile: dict, max_queries: int = 6) -> list[str]` — 让 DeepSeek 把兴趣+清单翻成针对性英文检索串。v1 只实现 `lens="research"` 的角度（"有没有更好的方法/最新论文"）；其它 lens 走同一函数、由 prompt 区分（Plan 2 补）。

- [ ] **Step 1: 写失败测试 `tests/test_query.py`**

```python
from diting.models import Interests
from diting.query import generate_queries

class _FakeClient:
    def __init__(self): self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return {"queries": ["fine-grained retrieval LoRA 2026", "MLX LoRA finetune best practice"]}

def test_generate_research_queries():
    c = _FakeClient()
    qs = generate_queries(c, "research",
                          Interests(("LoRA 微调",), ("MLX",), (), ("阈值改 0.3",)), {"topics": ["细粒度检索"]})
    assert len(qs) == 2 and "LoRA" in qs[0]
    assert "research" in c.seen[0]["content"].lower() or "论文" in c.seen[0]["content"]

def test_queries_capped(monkeypatch):
    c = _FakeClient()
    c.complete_json = lambda m, **k: {"queries": [f"q{i}" for i in range(20)]}
    assert len(generate_queries(c, "research", Interests((), (), (), ()), {}, max_queries=6)) == 6
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_query.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/query.py`**

```python
# src/diting/query.py
from __future__ import annotations
from diting.models import Interests

_LENS_PROMPT = {
    "research": "镜头=科研雷达。围绕用户的话题/卡点，生成用于在 arXiv/GitHub/HN 找"
                "'有没有更好的方法、最新论文、SOTA、best practice'的英文检索串。",
}

def generate_queries(client, lens: str, interests: Interests, profile: dict,
                     max_queries: int = 6) -> list[str]:
    lens_desc = _LENS_PROMPT.get(lens, _LENS_PROMPT["research"])
    sys = (lens_desc + " 偏好英文、精准、可直接喂搜索引擎。"
           '严格输出 JSON：{"queries": [".."]}')
    ctx = {"topics": list(interests.topics), "entities": list(interests.entities),
           "open_loops": list(interests.open_loops), "profile": profile}
    data = client.complete_json([
        {"role": "system", "content": sys},
        {"role": "user", "content": str(ctx)},
    ])
    return list(data.get("queries", []) or [])[:max_queries]
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_query.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/query.py tests/test_query.py && git commit -m "feat: 查询生成器（科研镜头）"`

---

### Task 8: 爬源 — arXiv + Hacker News

**Files:** Create `src/diting/sources/__init__.py`, `src/diting/sources/arxiv.py`, `src/diting/sources/hackernews.py` · Test `tests/test_sources_basic.py`

**Interfaces:**
- Produces:
  - `search_arxiv(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]`
  - `search_hn(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]`
  - 两者出错（网络/解析）时返回 `[]`，不抛（由编排层统计"没取到"）。`get` 可注入便于测试。

- [ ] **Step 1: 写失败测试 `tests/test_sources_basic.py`**

```python
from diting.sources.arxiv import search_arxiv
from diting.sources.hackernews import search_hn

class _Resp:
    def __init__(self, text="", payload=None): self.text = text; self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

_ATOM = """<feed xmlns="http://www.w3.org/2005/Atom">
<entry><title>Better Retrieval</title><id>http://arxiv.org/abs/2606.0001</id>
<summary>A new method.</summary></entry></feed>"""

def test_arxiv_parses_atom():
    out = search_arxiv("retrieval", get=lambda *a, **k: _Resp(text=_ATOM))
    assert out[0].title == "Better Retrieval"
    assert out[0].url == "http://arxiv.org/abs/2606.0001"
    assert out[0].source == "arxiv"

def test_hn_parses_json():
    payload = {"hits": [{"title": "Show HN: X", "url": "http://x", "objectID": "1"}]}
    out = search_hn("x", get=lambda *a, **k: _Resp(payload=payload))
    assert out[0].title == "Show HN: X" and out[0].source == "hackernews"

def test_source_degrades_on_error():
    def boom(*a, **k): raise RuntimeError("net down")
    assert search_arxiv("x", get=boom) == []
    assert search_hn("x", get=boom) == []
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_sources_basic.py -v` → FAIL

- [ ] **Step 3: 写三个文件**

```python
# src/diting/sources/__init__.py  （空）
```

```python
# src/diting/sources/arxiv.py
from __future__ import annotations
import xml.etree.ElementTree as ET
import httpx
from diting.models import Candidate

_NS = {"a": "http://www.w3.org/2005/Atom"}

def search_arxiv(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]:
    try:
        resp = get("http://export.arxiv.org/api/query",
                   params={"search_query": f"all:{query}", "max_results": max_results,
                           "sortBy": "submittedDate", "sortOrder": "descending"})
        resp.raise_for_status()
        root = ET.fromstring(resp.text)
    except Exception:
        return []
    out: list[Candidate] = []
    for e in root.findall("a:entry", _NS):
        title = (e.findtext("a:title", default="", namespaces=_NS) or "").strip()
        url = (e.findtext("a:id", default="", namespaces=_NS) or "").strip()
        summary = (e.findtext("a:summary", default="", namespaces=_NS) or "").strip()
        if title and url:
            out.append(Candidate(title=title, url=url, summary=summary, source="arxiv"))
    return out
```

```python
# src/diting/sources/hackernews.py
from __future__ import annotations
import httpx
from diting.models import Candidate

def search_hn(query: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]:
    try:
        resp = get("https://hn.algolia.com/api/v1/search",
                   params={"query": query, "tags": "story", "hitsPerPage": max_results})
        resp.raise_for_status()
        hits = resp.json().get("hits", [])
    except Exception:
        return []
    out: list[Candidate] = []
    for h in hits:
        title = (h.get("title") or "").strip()
        url = h.get("url") or f"https://news.ycombinator.com/item?id={h.get('objectID')}"
        if title:
            out.append(Candidate(title=title, url=url, summary="", source="hackernews"))
    return out
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_sources_basic.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/sources tests/test_sources_basic.py && git commit -m "feat: 爬源 arXiv + Hacker News"`

---

### Task 9: 爬源 — GitHub 仓库搜索

**Files:** Create `src/diting/sources/github.py` · Test `tests/test_github.py`

**Interfaces:**
- Produces: `search_github_repos(query: str, max_results: int = 5, *, get=httpx.get, token: str | None = None) -> list[Candidate]` — 按最近更新排序搜仓库。出错返回 `[]`。`token` 给则带 Authorization 提高限额。

- [ ] **Step 1: 写失败测试 `tests/test_github.py`**

```python
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
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_github.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/sources/github.py`**

```python
# src/diting/sources/github.py
from __future__ import annotations
import httpx
from diting.models import Candidate

def search_github_repos(query: str, max_results: int = 5, *, get=httpx.get,
                        token: str | None = None) -> list[Candidate]:
    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    try:
        resp = get("https://api.github.com/search/repositories",
                   params={"q": query, "sort": "updated", "order": "desc",
                           "per_page": max_results}, headers=headers)
        resp.raise_for_status()
        items = resp.json().get("items", [])
    except Exception:
        return []
    out: list[Candidate] = []
    for it in items:
        name = it.get("full_name") or ""
        url = it.get("html_url") or ""
        if name and url:
            out.append(Candidate(title=name, url=url,
                                 summary=it.get("description") or "", source="github"))
    return out
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_github.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/sources/github.py tests/test_github.py && git commit -m "feat: 爬源 GitHub 仓库搜索"`

---

### Task 10: 爬源 — searxng 元搜索 + 正文抽取

**Files:** Create `src/diting/sources/websearch.py` · Test `tests/test_websearch.py`

**Interfaces:**
- Produces:
  - `search_web(query: str, searxng_url: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]` — 调 searxng `format=json`。出错返回 `[]`。
  - `extract_main_text(html: str) -> str` — 用 trafilatura 抽正文（纯函数，无网络，便于测试）。

- [ ] **Step 1: 写失败测试 `tests/test_websearch.py`**

```python
from diting.sources.websearch import search_web, extract_main_text

class _Resp:
    def __init__(self, payload): self._p = payload
    def raise_for_status(self): pass
    def json(self): return self._p

def test_search_web_parses():
    payload = {"results": [{"title": "T", "url": "http://u", "content": "摘要"}]}
    out = search_web("q", "http://sx:8080", get=lambda *a, **k: _Resp(payload))
    assert out[0].title == "T" and out[0].source == "websearch" and out[0].summary == "摘要"

def test_extract_main_text():
    html = "<html><body><article><p>核心正文内容很长很长很长。</p></article></body></html>"
    assert "核心正文" in extract_main_text(html)
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_websearch.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/sources/websearch.py`**

```python
# src/diting/sources/websearch.py
from __future__ import annotations
import httpx
import trafilatura
from diting.models import Candidate

def search_web(query: str, searxng_url: str, max_results: int = 5, *, get=httpx.get) -> list[Candidate]:
    try:
        resp = get(f"{searxng_url.rstrip('/')}/search",
                   params={"q": query, "format": "json"})
        resp.raise_for_status()
        results = resp.json().get("results", [])[:max_results]
    except Exception:
        return []
    out: list[Candidate] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        if title and url:
            out.append(Candidate(title=title, url=url,
                                 summary=(r.get("content") or "").strip(), source="websearch"))
    return out

def extract_main_text(html: str) -> str:
    return trafilatura.extract(html) or ""
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_websearch.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/sources/websearch.py tests/test_websearch.py && git commit -m "feat: 爬源 searxng + 正文抽取"`

---

### Task 11: 爬取编排器

**Files:** Create `src/diting/crawl.py` · Test `tests/test_crawl.py`

**Interfaces:**
- Consumes: `Candidate`、一组"源函数"（签名 `(query: str) -> list[Candidate]`）。
- Produces: `run_crawl(queries: list[str], sources: dict[str, Callable]) -> tuple[list[Candidate], list[str]]` — 每个 query 跑每个源，汇总候选、**按 URL 去重保序**；某个源在所有 query 上都 0 结果 → 往 notes 记一条"{源名} 没取到"。

- [ ] **Step 1: 写失败测试 `tests/test_crawl.py`**

```python
from diting.models import Candidate
from diting.crawl import run_crawl

def test_crawl_merges_and_dedups():
    def src_a(q): return [Candidate(f"A-{q}", f"http://a/{q}", "", "a"),
                          Candidate("dup", "http://dup", "", "a")]
    def src_b(q): return [Candidate("dup", "http://dup", "", "b")]   # 同 URL 应被去重
    cands, notes = run_crawl(["q1", "q2"], {"a": src_a, "b": src_b})
    urls = [c.url for c in cands]
    assert urls.count("http://dup") == 1
    assert "http://a/q1" in urls and "http://a/q2" in urls
    assert notes == []

def test_crawl_notes_empty_source():
    def good(q): return [Candidate("x", "http://x", "", "good")]
    def empty(q): return []
    _, notes = run_crawl(["q"], {"good": good, "empty": empty})
    assert any("empty" in n for n in notes)
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_crawl.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/crawl.py`**

```python
# src/diting/crawl.py
from __future__ import annotations
from typing import Callable
from diting.models import Candidate

def run_crawl(queries: list[str],
              sources: dict[str, Callable[[str], list[Candidate]]]
              ) -> tuple[list[Candidate], list[str]]:
    seen: set[str] = set()
    merged: list[Candidate] = []
    counts: dict[str, int] = {name: 0 for name in sources}
    for q in queries:
        for name, fn in sources.items():
            for cand in fn(q):
                counts[name] += 1
                if cand.url in seen:
                    continue
                seen.add(cand.url)
                merged.append(cand)
    notes = [f"{name} 没取到" for name, n in counts.items() if n == 0]
    return merged, notes
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_crawl.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/crawl.py tests/test_crawl.py && git commit -m "feat: 爬取编排器（多源合并 + URL 去重）"`

---

### Task 12: 去重 + 新颖度判定

**Files:** Create `src/diting/novelty.py` · Test `tests/test_novelty.py`

> **v1 范围说明（诚实标注）**：spec 要求"回查 gbrain/graphify/Qdrant 砍已知"。那三套是独立服务/MCP，直连需嵌入与鉴权，复杂度高。**v1 先用一个完全本地、零依赖、且很有效的新颖度信号**：把"用户自己最近的工作"（兴趣画像/已推送）当作"已知库"，让 DeepSeek 判断每条候选是否对用户是新的——这正好实现"别告诉我我刚干过的事"。`judge_novelty` 留了 `known_context` 注入点，Plan 2 再把 gbrain/graphify/Qdrant 的回查结果拼进这个字符串即可，无需改接口。

**Interfaces:**
- Produces:
  - `filter_unpushed(candidates: list[Candidate], store: StateStore) -> list[Candidate]` — 砍掉跨天已推过的（按 URL）。
  - `judge_novelty(client, candidates: list[Candidate], known_context: str = "") -> list[Candidate]` — DeepSeek 返回"对用户为新"的子集（按 URL 过滤，保序）。

- [ ] **Step 1: 写失败测试 `tests/test_novelty.py`**

```python
from diting.models import Candidate
from diting.state import StateStore
from diting.novelty import filter_unpushed, judge_novelty

def _c(u): return Candidate(f"t{u}", u, "", "src")

def test_filter_unpushed(tmp_path):
    store = StateStore(str(tmp_path)); store.mark_pushed("http://old", "x")
    out = filter_unpushed([_c("http://old"), _c("http://new")], store)
    assert [c.url for c in out] == ["http://new"]

def test_judge_novelty_keeps_subset():
    class FakeClient:
        def complete_json(self, messages, **kw):
            return {"novel_urls": ["http://a"]}
    out = judge_novelty(FakeClient(), [_c("http://a"), _c("http://b")], known_context="ctx")
    assert [c.url for c in out] == ["http://a"]

def test_judge_novelty_empty_input_short_circuits():
    class Boom:
        def complete_json(self, *a, **k): raise AssertionError("不该调 LLM")
    assert judge_novelty(Boom(), [], "ctx") == []
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_novelty.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/novelty.py`**

```python
# src/diting/novelty.py
from __future__ import annotations
from diting.models import Candidate

def filter_unpushed(candidates: list[Candidate], store) -> list[Candidate]:
    return [c for c in candidates if not store.is_pushed(c.url)]

_SYSTEM = (
    "你在帮用户筛'对他是新的'信息。给你用户已经熟悉的背景，和一批候选。"
    "判断哪些候选对用户是**新的、值得看的**（不是他早就知道的）。"
    '严格输出 JSON：{"novel_urls": [".."]}，只放新的那些的 url。'
)

def judge_novelty(client, candidates: list[Candidate], known_context: str = "") -> list[Candidate]:
    if not candidates:
        return []
    listing = "\n".join(f"- {c.url} | {c.title} | {c.summary[:160]}" for c in candidates)
    data = client.complete_json([
        {"role": "system", "content": _SYSTEM},
        {"role": "user", "content": f"用户已知背景：\n{known_context}\n\n候选：\n{listing}"},
    ])
    novel = set(data.get("novel_urls", []) or [])
    return [c for c in candidates if c.url in novel]
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_novelty.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/novelty.py tests/test_novelty.py && git commit -m "feat: 跨天去重 + 新颖度判定"`

---

### Task 13: 合成器（候选 → 带"为何重要"的成品，空则诚实）

**Files:** Create `src/diting/synthesize.py` · Test `tests/test_synthesize.py`

**Interfaces:**
- Consumes: `DeepSeekClient`、`list[Candidate]`、`Interests`。
- Produces: `synthesize(client, lens: str, date: str, candidates: list[Candidate], interests: Interests, notes: list[str] = []) -> Report` — 让 DeepSeek 排序、为每条写 `one_liner` 和 `why_it_matters`（关联到用户做过的事），剔除不够格的。若无够格 → `Report(items=())` + note "今天这块没值得看的"。`notes` 把爬取层的"X 源没取到"透传进报告末尾。

- [ ] **Step 1: 写失败测试 `tests/test_synthesize.py`**

```python
from diting.models import Candidate, Interests, Report
from diting.synthesize import synthesize

_INT = Interests(("LoRA",), ("MLX",), (), ())

def test_synthesize_builds_ranked_items():
    class FakeClient:
        def complete_json(self, messages, **kw):
            return {"items": [{"url": "http://a", "title": "论文A", "one_liner": "一句话",
                               "why_it_matters": "和你昨天的 LoRA 微调直接相关"}]}
    cands = [Candidate("论文A", "http://a", "abs", "arxiv")]
    r = synthesize(FakeClient(), "research", "2026-06-18", cands, _INT)
    assert isinstance(r, Report) and not r.is_empty()
    assert r.items[0].why_it_matters.startswith("和你昨天")
    assert r.items[0].lens == "research"

def test_synthesize_empty_is_honest():
    class FakeClient:
        def complete_json(self, messages, **kw): return {"items": []}
    r = synthesize(FakeClient(), "research", "2026-06-18", [], _INT, notes=["github 没取到"])
    assert r.is_empty()
    assert any("没值得看" in n for n in r.notes)
    assert "github 没取到" in r.notes
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_synthesize.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/synthesize.py`**

```python
# src/diting/synthesize.py
from __future__ import annotations
from diting.models import Candidate, Interests, RankedItem, Report

_SYSTEM = (
    "你是用户的私人技术情报员（precision-first，宁缺毋滥）。从候选里挑出真正值得他看的，"
    "排序，并为每条写：one_liner（一句话摘要）、why_it_matters（为什么对**他**重要——"
    "尽量关联到他最近做的事/卡点）。不够格的直接不要。**绝不硬凑**，宁可全部舍弃。"
    '严格输出 JSON：{"items": [{"url","title","one_liner","why_it_matters"}]}'
)

def synthesize(client, lens: str, date: str, candidates: list[Candidate],
               interests: Interests, notes: list[str] = []) -> Report:
    notes = list(notes)
    items: tuple[RankedItem, ...] = ()
    if candidates:
        ctx = {"topics": list(interests.topics), "open_loops": list(interests.open_loops),
               "candidates": [{"url": c.url, "title": c.title, "summary": c.summary[:300],
                               "source": c.source} for c in candidates]}
        data = client.complete_json([
            {"role": "system", "content": _SYSTEM},
            {"role": "user", "content": str(ctx)},
        ])
        by_url = {c.url: c for c in candidates}
        items = tuple(
            RankedItem(title=it.get("title", ""), url=it.get("url", ""),
                       one_liner=it.get("one_liner", ""), why_it_matters=it.get("why_it_matters", ""),
                       source=by_url.get(it.get("url", ""), Candidate("", "", "", "?")).source, lens=lens)
            for it in data.get("items", []) if it.get("url")
        )
    if not items:
        notes.insert(0, "今天这块没值得看的")
    return Report(lens=lens, date=date, items=items, notes=tuple(notes))
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_synthesize.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/synthesize.py tests/test_synthesize.py && git commit -m "feat: 合成器（带为何重要 + 空则诚实）"`

---

### Task 14: 投递 — Obsidian + 飞书

**Files:** Create `src/diting/deliver/__init__.py`, `src/diting/deliver/obsidian_out.py`, `src/diting/deliver/feishu.py` · Test `tests/test_deliver.py`

> **已核对（2026-06-18）**：发私聊用 `lark-cli im +messages-send --user-id <ou_open_id> --text <msg>`（`--user-id`/`--chat-id` 二选一；`--text`/`--markdown` 二选一）。`feishu_target` 填用户 open_id。

**Interfaces:**
- Produces:
  - `LENS_LABEL: dict[str,str]`（如 `{"research": "🔭 科研雷达"}`）。
  - `write_report_to_inbox(report: Report, inbox_dir: str, now_ts: float) -> str` — 当天 `YYYY-MM-DD 谛听情报.md` 不存在则建（含 frontmatter），追加一段；返回文件路径。
  - `format_feishu_message(report: Report) -> str`（纯函数）。
  - `send_to_feishu(report: Report, target: str, *, run=subprocess.run) -> bool` — 调 lark-cli，returncode==0 返回 True。

- [ ] **Step 1: 写失败测试 `tests/test_deliver.py`**

```python
import os, time
from diting.models import RankedItem, Report
from diting.deliver.obsidian_out import write_report_to_inbox
from diting.deliver.feishu import format_feishu_message, send_to_feishu

_NOW = time.mktime(time.strptime("2026-06-18 10:05", "%Y-%m-%d %H:%M"))
_R = Report("research", "2026-06-18",
            (RankedItem("论文A", "http://a", "一句话", "和你 LoRA 相关", "arxiv", "research"),), ())

def test_obsidian_creates_then_appends(tmp_path):
    p = write_report_to_inbox(_R, str(tmp_path), _NOW)
    body = open(p, encoding="utf-8").read()
    assert "type: note" in body and "谛听情报" in body
    assert "🔭 科研雷达" in body and "http://a" in body and "和你 LoRA 相关" in body
    # 再投一份不应重建 frontmatter
    write_report_to_inbox(Report("research", "2026-06-18", (), ("今天这块没值得看的",)), str(tmp_path), _NOW)
    assert open(p, encoding="utf-8").read().count("type: note") == 1

def test_feishu_message_and_send():
    msg = format_feishu_message(_R)
    assert "论文A" in msg and "和你 LoRA 相关" in msg
    captured = {}
    def fake_run(argv, **kw):
        captured["argv"] = argv
        class R: returncode = 0
        return R()
    assert send_to_feishu(_R, "me", run=fake_run) is True
    assert "论文A" in " ".join(captured["argv"])
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_deliver.py -v` → FAIL

- [ ] **Step 3: 写三个文件**

```python
# src/diting/deliver/__init__.py
LENS_LABEL = {"research": "🔭 科研雷达", "loops": "🧩 悬而未决+反方", "trends": "🛰️ 趋势保鲜"}
```

```python
# src/diting/deliver/obsidian_out.py
from __future__ import annotations
import os, time
from diting.models import Report
from diting.deliver import LENS_LABEL

def _frontmatter(date: str) -> str:
    return (f"---\ntitle: {date} 谛听情报\ntype: note\nstatus: inbox\n"
            f"created: {date}\nlast_updated: {date}\n---\n\n# {date} 谛听情报\n")

def _section(report: Report, time_str: str) -> str:
    label = LENS_LABEL.get(report.lens, report.lens)
    lines = [f"\n## {time_str} {label}\n"]
    for it in report.items:
        lines.append(f"### [{it.title}]({it.url})")
        lines.append(f"- {it.one_liner}")
        lines.append(f"- **为什么对你重要**：{it.why_it_matters}")
        lines.append(f"- 来源：{it.source}\n")
    if report.is_empty():
        lines.append("_今天这块没值得看的。_\n")
    for n in report.notes:
        if n != "今天这块没值得看的":
            lines.append(f"> 注：{n}\n")
    return "\n".join(lines)

def write_report_to_inbox(report: Report, inbox_dir: str, now_ts: float) -> str:
    os.makedirs(inbox_dir, exist_ok=True)
    lt = time.localtime(now_ts)
    date = time.strftime("%Y-%m-%d", lt); time_str = time.strftime("%H:%M", lt)
    path = os.path.join(inbox_dir, f"{date} 谛听情报.md")
    with open(path, "a", encoding="utf-8") as f:
        if f.tell() == 0:
            f.write(_frontmatter(date))
        f.write(_section(report, time_str))
    return path
```

```python
# src/diting/deliver/feishu.py
from __future__ import annotations
import subprocess
from diting.models import Report
from diting.deliver import LENS_LABEL

def format_feishu_message(report: Report) -> str:
    label = LENS_LABEL.get(report.lens, report.lens)
    head = f"【谛听 · {label} · {report.date}】"
    if report.is_empty():
        return head + "\n今天这块没值得看的。"
    blocks = [head]
    for it in report.items:
        blocks.append(f"• {it.title}\n  {it.one_liner}\n  为什么重要：{it.why_it_matters}\n  {it.url}")
    return "\n".join(blocks)

def send_to_feishu(report: Report, target: str, *, run=subprocess.run) -> bool:
    msg = format_feishu_message(report)
    argv = ["lark-cli", "im", "+messages-send", "--user-id", target, "--text", msg]
    try:
        return run(argv, capture_output=True).returncode == 0
    except Exception:
        return False
```

- [ ] **Step 4: 运行确认通过** — `pytest tests/test_deliver.py -v` → PASS

- [ ] **Step 5: 提交** — `git add src/diting/deliver tests/test_deliver.py && git commit -m "feat: 投递 Obsidian + 飞书"`

---

### Task 15: 报告编排器 + CLI（端到端串通）

**Files:** Create `src/diting/runner.py`, `src/diting/__main__.py` · Test `tests/test_runner.py`

**Interfaces:**
- Consumes: 前面所有模块。
- Produces:
  - `build_sources(cfg) -> dict[str, Callable]` — 把 cfg 绑进四个源（arxiv/hn/github/websearch）。
  - `build_known_context(interests, profile) -> str` — v1 的"已知库"= 用户自己的近期工作。
  - `run_report(lens, cfg, client, store, *, now_ts, sources=None, feishu_run=subprocess.run) -> Report` — 串起整条流水线并投递、记已推送。
  - CLI：`python -m diting run --lens research`、`python -m diting seed-profile --from <file...>`。

- [ ] **Step 1: 写失败的端到端测试 `tests/test_runner.py`**（全 mock，不打网/不发飞书）

```python
import os, time
from diting.models import Candidate
from diting.config import Config
from diting.state import StateStore
from diting.runner import run_report

_NOW = time.mktime(time.strptime("2026-06-18 10:00", "%Y-%m-%d %H:%M"))

class RouterClient:
    """按 system prompt 关键词返回不同 JSON，模拟 DeepSeek 各步。"""
    def complete_json(self, messages, **kw):
        sysmsg = messages[0]["content"]
        if "兴趣" in sysmsg or "提炼" in sysmsg:
            return {"topics": ["LoRA"], "entities": ["MLX"], "open_loops": [], "decisions": []}
        if "queries" in sysmsg or "检索串" in sysmsg:
            return {"queries": ["lora finetune 2026"]}
        if "novel" in sysmsg or "新的" in sysmsg:
            return {"novel_urls": ["http://a"]}
        if "情报员" in sysmsg:
            return {"items": [{"url": "http://a", "title": "论文A",
                               "one_liner": "一句话", "why_it_matters": "和你 LoRA 相关"}]}
        return {}

def _cfg(tmp_path) -> Config:
    recs = tmp_path / "recs"; recs.mkdir()
    (recs / "today.md").write_text("今天搞 LoRA 微调", encoding="utf-8")
    return Config("http://x/v1", "deepseek-v4-pro", "DS", str(recs), 5,
                  "http://sx", "GH", str(tmp_path / "inbox"), "me", str(tmp_path / "state"))

def test_run_report_end_to_end(tmp_path):
    cfg = _cfg(tmp_path)
    os.utime(os.path.join(cfg.session_records_dir, "today.md"), (_NOW, _NOW))
    store = StateStore(cfg.state_dir)
    fake_sources = {"arxiv": lambda q: [Candidate("论文A", "http://a", "abs", "arxiv")]}
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_report("research", cfg, RouterClient(), store,
                        now_ts=_NOW, sources=fake_sources, feishu_run=fake_feishu)
    assert not report.is_empty() and report.items[0].url == "http://a"
    # Obsidian 落档
    assert os.path.exists(os.path.join(cfg.vault_inbox_dir, "2026-06-18 谛听情报.md"))
    # 飞书发了
    assert "论文A" in " ".join(sent["argv"])
    # 已推送去重生效：再跑一次，该 URL 被 filter_unpushed 砍掉 → 空报告
    report2 = run_report("research", cfg, RouterClient(), store,
                         now_ts=_NOW, sources=fake_sources, feishu_run=fake_feishu)
    assert report2.is_empty()
```

- [ ] **Step 2: 运行确认失败** — `pytest tests/test_runner.py -v` → FAIL

- [ ] **Step 3: 写 `src/diting/runner.py`**

```python
# src/diting/runner.py
from __future__ import annotations
import os, time, subprocess
from diting.models import Interests, Report
from diting.signal.obsidian import collect_session_records
from diting.signal.distill import distill_interests
from diting.signal.profile import fatten_profile
from diting.query import generate_queries
from diting.crawl import run_crawl
from diting.novelty import filter_unpushed, judge_novelty
from diting.synthesize import synthesize
from diting.deliver.obsidian_out import write_report_to_inbox
from diting.deliver.feishu import send_to_feishu
from diting.sources.arxiv import search_arxiv
from diting.sources.hackernews import search_hn
from diting.sources.github import search_github_repos
from diting.sources.websearch import search_web

def build_sources(cfg) -> dict:
    gh_token = os.environ.get(cfg.github_token_env)
    return {
        "arxiv": lambda q: search_arxiv(q),
        "hackernews": lambda q: search_hn(q),
        "github": lambda q: search_github_repos(q, token=gh_token),
        "websearch": lambda q: search_web(q, cfg.searxng_url),
    }

def build_known_context(interests: Interests, profile: dict) -> str:
    return ("用户最近在搞：" + "、".join(interests.topics)
            + "；常用栈/工具：" + "、".join(profile.get("stack", []) + profile.get("tools", [])))

def run_report(lens, cfg, client, store, *, now_ts=None, sources=None,
               feishu_run=subprocess.run) -> Report:
    now_ts = now_ts if now_ts is not None else time.time()
    signals = collect_session_records(cfg.session_records_dir, cfg.lookback_days, now_ts)
    interests = distill_interests(client, signals) if signals else Interests((), (), (), ())
    profile = fatten_profile(store.load_profile(), interests)
    store.save_profile(profile)
    queries = generate_queries(client, lens, interests, profile)
    candidates, notes = run_crawl(queries, sources or build_sources(cfg))
    candidates = filter_unpushed(candidates, store)
    candidates = judge_novelty(client, candidates, build_known_context(interests, profile))
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    report = synthesize(client, lens, date, candidates, interests, notes)
    write_report_to_inbox(report, cfg.vault_inbox_dir, now_ts)
    send_to_feishu(report, cfg.feishu_target, run=feishu_run)
    for it in report.items:
        store.mark_pushed(it.url, it.title)
    return report
```

- [ ] **Step 4: 写 `src/diting/__main__.py`**

```python
# src/diting/__main__.py
from __future__ import annotations
import argparse
from diting.config import load_config
from diting.llm import DeepSeekClient
from diting.state import StateStore
from diting.runner import run_report
from diting.signal.profile import seed_profile

def _client(cfg):
    return DeepSeekClient(cfg.deepseek_base_url, cfg.deepseek_api_key, cfg.deepseek_model)

def main():
    ap = argparse.ArgumentParser(prog="diting")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run"); r.add_argument("--lens", default="research")
    s = sub.add_parser("seed-profile"); s.add_argument("--from", dest="files", nargs="+", required=True)
    args = ap.parse_args()
    cfg = load_config()
    if args.cmd == "run":
        store = StateStore(cfg.state_dir)
        report = run_report(args.lens, cfg, _client(cfg), store)
        print(f"[{report.lens}] {report.date}: {len(report.items)} 条" +
              ("" if report.items else " — 今天这块没值得看的"))
    elif args.cmd == "seed-profile":
        store = StateStore(cfg.state_dir)
        texts = [open(f, encoding="utf-8").read() for f in args.files]
        prof = seed_profile(_client(cfg), texts)
        store.save_profile(prof)
        print("关注清单已生成：", prof)

if __name__ == "__main__":
    main()
```

- [ ] **Step 5: 运行确认通过** — `pytest tests/test_runner.py -v` → PASS

- [ ] **Step 6: 全量回归** — `pytest -q` → 全绿

- [ ] **Step 7: 提交** — `git add src/diting/runner.py src/diting/__main__.py tests/test_runner.py && git commit -m "feat: 报告编排器 + CLI，端到端串通"`

---

## 手动验收（端到端真跑一次）

1. `cp config.example.yaml config.yaml`，填真实值（DeepSeek endpoint/model、会话记录目录、searxng、Inbox 路径、feishu target）。
2. `export DEEPSEEK_API_KEY=...`（复用 OpenClaw 那把）、`export GITHUB_TOKEN=...`（可选）。
3. `python -m diting seed-profile --from ~/.claude/CLAUDE.md <救命手册.md> <底座手册.md>` → 看 `state/interest_profile.yaml`。
4. `python -m diting run --lens research` → 检查飞书收到 + `Inbox/2026-06-18 谛听情报.md` 落档。
5. 抽查条目：是不是关联到你最近做的事、是不是你没见过的（precision 自检）。

---

## Self-Review（计划对照 spec）

- **§4 六段流水线**：Task 4–15 逐段覆盖 ✅
- **§5 三镜头**：v1 落 research 镜头；loops/trends 走同一 `generate_queries`/`synthesize`，Plan 2 补 prompt 分支与 versions.json（已在 Task 7/12 留扩展点）✅
- **§6 信号肥料**：动态肥料（Obsidian 会话记录）Task 4；静态肥料+关注清单 Task 6 ✅；claude-mem/Qdrant 作为 v1.1 增源（`distill` 已能吃任意 `SignalItem`）。
- **§9 去重·新颖度**：Task 12（跨天 + 新颖度判定）✅，gbrain/graphify/Qdrant 回查留 `known_context` 注入点（已诚实标注）。
- **§10 合成 precision-first**：Task 13 空则诚实 ✅
- **§11 双通道投递**：Task 14 ✅
- **§12 全程 DeepSeek V4 Pro**：所有 LLM 走单一 `DeepSeekClient` ✅
- **§13 状态**：pushed.db + interest_profile.yaml（Task 2）✅；versions.json 属 trends 镜头，Plan 2 建。
- **类型一致性**：`Interests/Candidate/RankedItem/Report` 全程同名同签名 ✅
- **占位符扫描**：无 TBD/TODO 占位；每步含可运行代码 ✅

