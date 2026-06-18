# 谛听 阶段二：dig 自动深挖镜头 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给谛听新增一个 `dig` 镜头——每天自动挑一个话题，复用阶段一的抓取内核多角度搜+深抓正文，喂 DeepSeek 综合成一份结构化中文长资料，落 Obsidian + 飞书发短通知。

**Architecture:** 选题（`signal/dig_topics.py`：想挖清单优先、空了从兴趣自动选、去重、无题返回 None）→ 编排（`dig.py`：生成多角度查询 → `search_engine` 搜 → `fetch_text` 抓 top-N 正文 → `synthesize_dig` 喂 DeepSeek 综合）→ 产出（`deliver/dig_out.py` 写 reference-manual 长文 + `feishu.send_dig_notice` 短通知）。dig 走**独立入口 `run_dig`**（产出是长文 `DigReport`，与 research 的 `Report`/`RankedItem` 不同，不复用 `run_report`）。投递成功后才 `mark_dug`（沿用 trends 快照"投递后推进"原则）。

**Tech Stack:** Python 3.11、scrapling（经阶段一 `fetch.py` 封装）、DeepSeek V4 Pro、pyyaml、pytest。

> 依据 `docs/superpowers/specs/2026-06-18-diting-scrapling-deepdig-design.md` 第 4.3 节。**第一版不含 gh 扒代码仓**（spec 标"可选"，YAGNI——先验证核心闭环：选题→搜→抓→综合→产出，gh 留后续）。复用阶段一已上线的 `src/diting/sources/fetch.py`（`fetch_text`、`search_engine`）。

## Global Constraints

- **跑 Python 一律用 framework python 全路径**：`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`；测试 `… -m pytest`。绝不裸用 `python`/`pytest`。
- **不可变**：`models.py` 全 `@dataclass(frozen=True)`；新增 `DigReport` 同样 frozen。
- **precision-first**：选不到题 / 全部来源抓空 / 综合失败 → 产出空 `DigReport`，**不投递、不登记**（沿用空报告不刷飞书）。
- **反爬稳妥派**：抓正文复用 `fetch_text`（反爬域走 stealthy，本机失败就跳过，绝不硬刚真 Chrome）。
- **投递成功才 `mark_dug`**：Obsidian + 飞书都发出后才把话题登记为已挖（投递失败下次重试，不丢话题）。
- **防失控**：每次只挖 1 题；来源数封顶 `dig_max_sources`（默认 12）；喂模型的正文截断。
- **单测不得联网**：选题/查询/综合/投递全靠注入假 client、假 fetch、假 search。
- **Obsidian 规范**：长文 `type: reference-manual`，5 字段 frontmatter（title/type/status/created/last_updated），文件名带日期前缀，放 `dig_vault_dir`。
- 中文注释/文案，与现有代码风格一致。

## 文件结构（本阶段触及）

- **Modify** `src/diting/models.py` — 新增 `DigReport(topic, date, markdown, one_liner, source_count)` frozen dataclass + `is_empty()`。
- **Modify** `src/diting/state.py` — `StateStore` 新增 `is_dug(topic)` / `mark_dug(topic)`（存 `state/dug_topics.json`）。
- **Modify** `src/diting/config.py` + `config.example.yaml` — 新增 `dig_vault_dir`、`dig_max_sources`、`dig_queue_path`。
- **Create** `src/diting/signal/dig_topics.py` — `select_dig_topic(store, interests, queue_path) -> str | None`。
- **Create** `src/diting/dig.py` — `generate_dig_queries`、`synthesize_dig`、`run_dig`。
- **Create** `src/diting/deliver/dig_out.py` — `write_dig_to_vault(report, dig_vault_dir, now_ts) -> str`。
- **Modify** `src/diting/deliver/feishu.py` — 新增 `send_dig_notice(report, target, doc_path, *, run)`。
- **Modify** `src/diting/__main__.py` — `run --lens dig` 路由到 `run_dig`。
- **Create** `scripts/launchd/ai.diting.dig.plist` + **Modify** `scripts/install-launchd.sh` / `scripts/deploy.sh` — 每天 20:00 跑 dig。

---

### Task 1: DigReport 模型 + StateStore 已挖登记

**Files:**
- Modify: `src/diting/models.py`
- Modify: `src/diting/state.py`
- Test: `tests/test_models.py`、`tests/test_state.py`

**Interfaces:**
- Produces: `DigReport(topic: str, date: str, markdown: str, one_liner: str, source_count: int)` frozen，`is_empty() -> bool`（`markdown` 为空即空报告）。`StateStore.is_dug(topic: str) -> bool` / `StateStore.mark_dug(topic: str) -> None`（持久化到 `state/dug_topics.json`）。

- [ ] **Step 1: 写失败测试（DigReport）**

在 `tests/test_models.py` 末尾追加：

```python
def test_dig_report_empty_when_no_markdown():
    from diting.models import DigReport
    r = DigReport(topic="RAG", date="2026-06-18", markdown="", one_liner="", source_count=0)
    assert r.is_empty()
    r2 = DigReport(topic="RAG", date="2026-06-18", markdown="# 正文", one_liner="一句话", source_count=5)
    assert not r2.is_empty()
```

- [ ] **Step 2: 写失败测试（dug 登记）**

在 `tests/test_state.py` 末尾追加：

```python
def test_dug_topics_roundtrip(tmp_path):
    from diting.state import StateStore
    s = StateStore(str(tmp_path / "state"))
    assert s.is_dug("RAG 新做法") is False
    s.mark_dug("RAG 新做法")
    assert s.is_dug("RAG 新做法") is True
    # 持久化：换一个 StateStore 实例仍记得
    s2 = StateStore(str(tmp_path / "state"))
    assert s2.is_dug("RAG 新做法") is True
```

- [ ] **Step 3: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_models.py::test_dig_report_empty_when_no_markdown tests/test_state.py::test_dug_topics_roundtrip -v`
Expected: FAIL（`ImportError: DigReport` / `AttributeError: is_dug`）。

- [ ] **Step 4: 实现 DigReport**

`src/diting/models.py` 末尾追加：

```python
@dataclass(frozen=True)
class DigReport:
    topic: str
    date: str
    markdown: str
    one_liner: str
    source_count: int

    def is_empty(self) -> bool:
        return not self.markdown
```

- [ ] **Step 5: 实现 dug 登记**

`src/diting/state.py` 的 `StateStore.__init__` 末尾（`self._versions = ...` 之后）加：

```python
        self._dug = os.path.join(self.dir, "dug_topics.json")
```

并在类内新增两个方法：

```python
    def _load_dug(self) -> list[str]:
        if not os.path.exists(self._dug):
            return []
        try:
            with open(self._dug, "r", encoding="utf-8") as f:
                return json.load(f) or []
        except (json.JSONDecodeError, OSError):
            return []

    def is_dug(self, topic: str) -> bool:
        return topic in self._load_dug()

    def mark_dug(self, topic: str) -> None:
        dug = self._load_dug()
        if topic not in dug:
            dug.append(topic)
        try:
            with open(self._dug, "w", encoding="utf-8") as f:
                json.dump(dug, f, ensure_ascii=False)
        except OSError as e:
            print(f"[谛听] 写 dug_topics.json 失败：{e}")
```

- [ ] **Step 6: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿（73 + 2 新）。

- [ ] **Step 7: 提交**

```bash
git add src/diting/models.py src/diting/state.py tests/test_models.py tests/test_state.py
git commit -m "feat: DigReport 模型 + StateStore 已挖话题登记"
```

---

### Task 2: config 增加 dig 三字段

**Files:**
- Modify: `src/diting/config.py`
- Modify: `config.example.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.dig_vault_dir: str`、`Config.dig_max_sources: int`（默认 12）、`Config.dig_queue_path: str`（默认 `<state_dir>/dig_queue.yaml`）。从 `raw` 读，缺省走默认。

- [ ] **Step 1: 写失败测试**

在 `tests/test_config.py` 追加：

```python
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
    assert cfg.dig_vault_dir == "/inbox"            # 缺省退回 inbox 同级（见实现）
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -k dig -v`
Expected: FAIL（`AttributeError: dig_max_sources`）。

- [ ] **Step 3: 加字段**

`src/diting/config.py` 的 `Config` 末尾（`known_antibot_domains` 之后）加：

```python
    dig_vault_dir: str = ""
    dig_max_sources: int = 12
    dig_queue_path: str = ""
```

`load_config` 的 `Config(...)` 构造里，在 `known_antibot_domains=...` 之后补：

```python
            dig_vault_dir=raw["deliver"].get("dig_vault_dir", raw["deliver"]["vault_inbox_dir"]),
            dig_max_sources=int(raw["deliver"].get("dig_max_sources", 12)),
            dig_queue_path=raw.get("dig_queue_path", os.path.join(raw["state_dir"], "dig_queue.yaml")),
```

- [ ] **Step 4: 更新 config.example.yaml**

把 `config.example.yaml` 的 `deliver:` 段补两行：

```yaml
deliver:
  vault_inbox_dir: "/Users/<dev-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/Inbox"
  feishu_target: "ou_你的openid"
  dig_vault_dir: "/Users/<dev-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/谛听深挖"  # dig 深挖长资料落盘目录
  dig_max_sources: 12                       # dig 每轮最多抓几篇来源
```

- [ ] **Step 5: 跑测试 + 提交**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -v`
Expected: 全 PASS。

```bash
git add src/diting/config.py config.example.yaml tests/test_config.py
git commit -m "feat: config 增加 dig_vault_dir / dig_max_sources / dig_queue_path"
```

---

### Task 3: dig 选题 select_dig_topic

**Files:**
- Create: `src/diting/signal/dig_topics.py`
- Test: `tests/test_dig_topics.py`

**Interfaces:**
- Consumes: `StateStore.is_dug`（Task 1）、`Interests`（models）。
- Produces: `select_dig_topic(store, interests: Interests, queue_path: str) -> str | None` — 想挖清单(yaml list 或 `{topics: [...]}`)优先取第一个未挖过的；清单空/缺则从 `interests.topics` 取第一个未挖过的；都没有返回 `None`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_dig_topics.py`：

```python
import yaml
from diting.models import Interests
from diting.signal.dig_topics import select_dig_topic


class _Store:
    def __init__(self, dug=()):
        self._dug = set(dug)
    def is_dug(self, t):
        return t in self._dug


def _queue(tmp_path, items):
    p = tmp_path / "dig_queue.yaml"
    p.write_text(yaml.safe_dump(items, allow_unicode=True), encoding="utf-8")
    return str(p)


def test_select_prefers_queue(tmp_path):
    q = _queue(tmp_path, ["话题A", "话题B"])
    assert select_dig_topic(_Store(), Interests(("兴趣X",), (), (), ()), q) == "话题A"

def test_select_skips_dug_in_queue(tmp_path):
    q = _queue(tmp_path, ["话题A", "话题B"])
    assert select_dig_topic(_Store(dug={"话题A"}), Interests((), (), (), ()), q) == "话题B"

def test_select_falls_back_to_interests_when_queue_empty(tmp_path):
    q = _queue(tmp_path, [])
    assert select_dig_topic(_Store(), Interests(("兴趣X", "兴趣Y"), (), (), ()), q) == "兴趣X"

def test_select_returns_none_when_all_dug(tmp_path):
    assert select_dig_topic(_Store(dug={"兴趣X"}), Interests(("兴趣X",), (), (), ()), "/nonexistent") is None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig_topics.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.signal.dig_topics`）。

- [ ] **Step 3: 实现**

创建 `src/diting/signal/dig_topics.py`：

```python
# src/diting/signal/dig_topics.py
from __future__ import annotations
import os
import yaml
from diting.models import Interests


def _load_queue(queue_path: str) -> list[str]:
    if not queue_path or not os.path.exists(queue_path):
        return []
    try:
        with open(queue_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except (OSError, yaml.YAMLError):
        return []
    if isinstance(data, dict):
        data = data.get("topics") or []
    if not isinstance(data, list):
        return []
    return [str(t).strip() for t in data if str(t).strip()]


def select_dig_topic(store, interests: Interests, queue_path: str) -> str | None:
    """选一个要深挖的话题：想挖清单优先取第一个未挖过的；清单空/缺则从兴趣 topics 取第一个未挖过的；都没有返回 None。"""
    for topic in _load_queue(queue_path):
        if not store.is_dug(topic):
            return topic
    for topic in interests.topics:
        if not store.is_dug(topic):
            return topic
    return None
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig_topics.py -q && /Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/signal/dig_topics.py tests/test_dig_topics.py
git commit -m "feat: dig 选题 select_dig_topic（清单优先/兴趣兜底/去重/无题返 None）"
```

---

### Task 4: dig 查询生成 generate_dig_queries

**Files:**
- Create: `src/diting/dig.py`
- Test: `tests/test_dig.py`

**Interfaces:**
- Produces: `generate_dig_queries(client, topic: str, max_queries: int = 6) -> list[str]` — 围绕单个话题生成多角度英文检索关键词串（论文/实战/实现/坑），截断到 `max_queries`。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_dig.py`：

```python
from diting.dig import generate_dig_queries


class _Client:
    def __init__(self, payload):
        self._p = payload
        self.seen = None
    def complete_json(self, messages, **kw):
        self.seen = messages
        return self._p


def test_generate_dig_queries_returns_and_caps():
    c = _Client({"queries": ["q1", "q2", "q3", "q4", "q5", "q6", "q7"]})
    out = generate_dig_queries(c, "RAG 新做法", max_queries=6)
    assert out == ["q1", "q2", "q3", "q4", "q5", "q6"]
    # 话题被传给了模型
    assert "RAG 新做法" in c.seen[1]["content"]

def test_generate_dig_queries_empty_payload():
    assert generate_dig_queries(_Client({}), "X") == []
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig.py -k queries -v`
Expected: FAIL（`ModuleNotFoundError: diting.dig`）。

- [ ] **Step 3: 实现**

创建 `src/diting/dig.py`：

```python
# src/diting/dig.py
from __future__ import annotations
import json

_DIG_QUERY_SYSTEM = (
    "你在帮用户深挖一个技术话题。围绕给定话题，生成 4-6 个多角度英文检索关键词串，"
    "覆盖：综述/论文、最佳实践/实战经验、开源实现、常见坑/对比。每条是简短英文关键词组(3-6 词)，"
    "不要整句话。严格输出 JSON：{\"queries\": [\"keyword phrase\", ...]}"
)


def generate_dig_queries(client, topic: str, max_queries: int = 6) -> list[str]:
    data = client.complete_json([
        {"role": "system", "content": _DIG_QUERY_SYSTEM},
        {"role": "user", "content": topic},
    ])
    return list(data.get("queries", []) or [])[:max_queries]
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/diting/dig.py tests/test_dig.py
git commit -m "feat: dig 查询生成 generate_dig_queries（围绕话题多角度）"
```

---

### Task 5: dig 综合 synthesize_dig

**Files:**
- Modify: `src/diting/dig.py`
- Test: `tests/test_dig.py`

**Interfaces:**
- Consumes: `DigReport`（Task 1）、`Candidate.body/summary`（阶段一）。
- Produces: `synthesize_dig(client, topic: str, date: str, candidates: list, *, body_limit: int = 2000) -> DigReport` — 把候选正文喂 DeepSeek 综合成结构化中文长资料（markdown）+ one_liner；空候选返回空 `DigReport`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_dig.py` 追加：

```python
from diting.models import Candidate, DigReport
from diting.dig import synthesize_dig

def test_synthesize_dig_builds_report():
    class C:
        def __init__(self): self.seen = None
        def complete_json(self, messages, **kw):
            self.seen = messages
            return {"one_liner": "RAG 有三种新路线", "markdown": "## 概览\n正文..."}
    c = C()
    cands = [Candidate("论文A", "http://a", "摘要", "websearch", body="正文关键词QWE")]
    r = synthesize_dig(c, "RAG 新做法", "2026-06-18", cands)
    assert isinstance(r, DigReport)
    assert r.markdown.startswith("## 概览") and r.one_liner == "RAG 有三种新路线"
    assert r.source_count == 1 and not r.is_empty()
    assert "正文关键词QWE" in c.seen[1]["content"]   # 喂了正文

def test_synthesize_dig_empty_candidates_returns_empty():
    class C:
        def complete_json(self, m, **k): raise AssertionError("空候选不该调模型")
    r = synthesize_dig(C(), "RAG", "2026-06-18", [])
    assert r.is_empty() and r.source_count == 0
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig.py -k synthesize -v`
Expected: FAIL（`ImportError: synthesize_dig`）。

- [ ] **Step 3: 实现**

`src/diting/dig.py` 顶部 import 区改为：

```python
from __future__ import annotations
import json
from diting.models import Candidate, DigReport
```

文件追加：

```python
_DIG_SYNTH_SYSTEM = (
    "你是用户的私人技术情报研究员（precision-first，宁缺毋滥）。基于给定话题和抓取到的多篇来源正文，"
    "综合成一份结构化中文长资料 markdown。结构：## 概览 / ## 关键论文与项目（带链接+一句话价值）/ "
    "## 核心知识（分主题）/ ## 对你项目的直接建议 / ## 跨来源共识与分歧。只用提供的来源，不编造。"
    "另给一句话总括 one_liner。严格输出 JSON：{\"one_liner\": \"..\", \"markdown\": \"..完整 markdown..\"}"
)


def synthesize_dig(client, topic: str, date: str, candidates: list,
                   *, body_limit: int = 2000) -> DigReport:
    if not candidates:
        return DigReport(topic=topic, date=date, markdown="", one_liner="", source_count=0)
    sources = [{"title": c.title, "url": c.url, "text": (c.body or c.summary)[:body_limit]}
               for c in candidates]
    data = client.complete_json([
        {"role": "system", "content": _DIG_SYNTH_SYSTEM},
        {"role": "user", "content": json.dumps({"topic": topic, "sources": sources}, ensure_ascii=False)},
    ])
    return DigReport(
        topic=topic, date=date,
        markdown=(data.get("markdown") or "").strip(),
        one_liner=(data.get("one_liner") or "").strip(),
        source_count=len(candidates),
    )
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/dig.py tests/test_dig.py
git commit -m "feat: dig 综合 synthesize_dig（多源正文→结构化中文长资料）"
```

---

### Task 6: dig 产出 Obsidian reference-manual 长文

**Files:**
- Create: `src/diting/deliver/dig_out.py`
- Test: `tests/test_dig_out.py`

**Interfaces:**
- Consumes: `DigReport`（Task 1）。
- Produces: `write_dig_to_vault(report: DigReport, dig_vault_dir: str, now_ts: float) -> str` — 在 `dig_vault_dir` 写 `<date> 谛听深挖 <topic>.md`（5 字段 frontmatter，`type: reference-manual`），返回路径。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_dig_out.py`：

```python
import os, time
from diting.models import DigReport
from diting.deliver.dig_out import write_dig_to_vault

_NOW = time.mktime(time.strptime("2026-06-18 20:00", "%Y-%m-%d %H:%M"))

def test_write_dig_creates_reference_manual(tmp_path):
    report = DigReport(topic="RAG 新做法", date="2026-06-18",
                       markdown="## 概览\n正文内容", one_liner="一句话", source_count=3)
    path = write_dig_to_vault(report, str(tmp_path / "谛听深挖"), _NOW)
    assert os.path.exists(path)
    assert path.endswith("2026-06-18 谛听深挖 RAG 新做法.md")
    text = open(path, encoding="utf-8").read()
    assert "type: reference-manual" in text
    assert "title: 2026-06-18 谛听深挖 · RAG 新做法" in text
    assert "## 概览\n正文内容" in text

def test_write_dig_sanitizes_slash_in_topic(tmp_path):
    report = DigReport(topic="A/B 测试", date="2026-06-18",
                       markdown="x", one_liner="y", source_count=1)
    path = write_dig_to_vault(report, str(tmp_path / "d"), _NOW)
    # 话题里的 / 不能变成路径分隔符
    assert os.path.basename(path) == "2026-06-18 谛听深挖 A／B 测试.md"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig_out.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.deliver.dig_out`）。

- [ ] **Step 3: 实现**

创建 `src/diting/deliver/dig_out.py`：

```python
# src/diting/deliver/dig_out.py
from __future__ import annotations
import os
import time
from diting.models import DigReport


def _frontmatter(report: DigReport) -> str:
    return (f"---\ntitle: {report.date} 谛听深挖 · {report.topic}\n"
            f"type: reference-manual\nstatus: active\n"
            f"created: {report.date}\nlast_updated: {report.date}\n---\n\n"
            f"# {report.topic}\n\n"
            f"> 谛听自动深挖 · {report.date} · {report.source_count} 篇来源\n\n")


def write_dig_to_vault(report: DigReport, dig_vault_dir: str, now_ts: float) -> str:
    os.makedirs(dig_vault_dir, exist_ok=True)
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    safe_topic = report.topic.replace("/", "／").replace("\\", "＼").strip()
    path = os.path.join(dig_vault_dir, f"{date} 谛听深挖 {safe_topic}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(_frontmatter(report))
        f.write(report.markdown)
        f.write("\n")
    return path
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig_out.py -v`
Expected: PASS。

- [ ] **Step 5: 提交**

```bash
git add src/diting/deliver/dig_out.py tests/test_dig_out.py
git commit -m "feat: dig 产出 Obsidian reference-manual 长文"
```

---

### Task 7: dig 飞书短通知 send_dig_notice

**Files:**
- Modify: `src/diting/deliver/feishu.py`
- Test: `tests/test_deliver.py`

**Interfaces:**
- Consumes: `DigReport`（Task 1）。
- Produces: `format_dig_notice(report: DigReport, doc_path: str) -> str`、`send_dig_notice(report: DigReport, target: str, doc_path: str, *, run=subprocess.run) -> bool` — 飞书短通知（话题+one_liner+文档路径），走 `--as bot`。

- [ ] **Step 1: 写失败测试**

在 `tests/test_deliver.py` 追加：

```python
from diting.models import DigReport
from diting.deliver.feishu import format_dig_notice, send_dig_notice

def test_format_dig_notice_has_topic_oneliner_path():
    r = DigReport(topic="RAG 新做法", date="2026-06-18", markdown="...", one_liner="三条路线", source_count=4)
    msg = format_dig_notice(r, "/vault/谛听深挖/2026-06-18 谛听深挖 RAG 新做法.md")
    assert "RAG 新做法" in msg and "三条路线" in msg
    assert "谛听深挖 RAG 新做法.md" in msg and "4" in msg

def test_send_dig_notice_uses_bot():
    r = DigReport(topic="RAG", date="2026-06-18", markdown="x", one_liner="y", source_count=1)
    captured = {}
    def fake_run(argv, **kw):
        captured["argv"] = argv
        class R: returncode = 0
        return R()
    ok = send_dig_notice(r, "ou_me", "/p.md", run=fake_run)
    assert ok is True
    assert "--as" in captured["argv"] and "bot" in captured["argv"]
    assert "ou_me" in captured["argv"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_deliver.py -k dig -v`
Expected: FAIL（`ImportError: format_dig_notice`）。

- [ ] **Step 3: 实现**

`src/diting/deliver/feishu.py` 顶部 import 区把 `from diting.models import Report` 改为 `from diting.models import Report, DigReport`，文件末尾追加：

```python
def format_dig_notice(report: DigReport, doc_path: str) -> str:
    return (f"【谛听 · 🔬 深挖 · {report.date}】{report.topic}\n"
            f"{report.one_liner}\n"
            f"📄 {doc_path}（{report.source_count} 篇来源）")


def send_dig_notice(report: DigReport, target: str, doc_path: str, *, run=subprocess.run) -> bool:
    msg = format_dig_notice(report, doc_path)
    # 同 send_to_feishu：机器人身份私聊才会弹出+提醒
    argv = ["lark-cli", "im", "+messages-send", "--as", "bot", "--user-id", target, "--text", msg]
    try:
        return run(argv, capture_output=True).returncode == 0
    except Exception:
        return False
```

- [ ] **Step 4: 跑测试确认通过 + 回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/deliver/feishu.py tests/test_deliver.py
git commit -m "feat: dig 飞书短通知 send_dig_notice（--as bot）"
```

---

### Task 8: dig 编排 run_dig + CLI 路由

**Files:**
- Modify: `src/diting/dig.py`
- Modify: `src/diting/__main__.py`
- Test: `tests/test_dig.py`

**Interfaces:**
- Consumes: `collect_session_records`、`distill_interests`、`select_dig_topic`（Task 3）、`generate_dig_queries`（Task 4）、`synthesize_dig`（Task 5）、`search_engine`/`fetch_text`（阶段一）、`enrich_bodies`（阶段一 crawl.py）、`write_dig_to_vault`（Task 6）、`send_dig_notice`（Task 7）。
- Produces: `run_dig(cfg, client, store, *, now_ts=None, search=None, fetch=None, feishu_run=subprocess.run) -> DigReport` — 选题→多角度搜→抓 top-`dig_max_sources` 正文→综合→Obsidian+飞书投递→投递成功后 `mark_dug`。无题/空一律不投递不登记。CLI `run --lens dig` 路由到它。

- [ ] **Step 1: 写失败测试（端到端 + 无题跳过）**

在 `tests/test_dig.py` 追加：

```python
import time, types, os
import yaml
from diting.state import StateStore
from diting.dig import run_dig

_NOW = time.mktime(time.strptime("2026-06-18 20:00", "%Y-%m-%d %H:%M"))

def _dig_cfg(tmp_path, queue_topics=("RAG 新做法",)):
    recs = tmp_path / "recs"; recs.mkdir()
    (recs / "t.md").write_text("今天搞 RAG", encoding="utf-8")
    os.utime(str(recs / "t.md"), (_NOW, _NOW))
    qp = tmp_path / "dig_queue.yaml"
    qp.write_text(yaml.safe_dump(list(queue_topics), allow_unicode=True), encoding="utf-8")
    return types.SimpleNamespace(
        session_records_dir=str(recs), lookback_days=5,
        dig_queue_path=str(qp), dig_max_sources=12, known_antibot_domains=(),
        dig_vault_dir=str(tmp_path / "vault"), feishu_target="ou_me",
    )

class _DigRouter:
    def complete_json(self, messages, **kw):
        s = messages[0]["content"]
        if "兴趣" in s or "提炼" in s:
            return {"topics": ["RAG 新做法"], "entities": [], "open_loops": [], "decisions": []}
        if "queries" in s or "检索" in s:
            return {"queries": ["rag new 2026"]}
        if "研究员" in s:
            return {"one_liner": "三条路线", "markdown": "## 概览\n正文"}
        raise ValueError(f"unexpected prompt: {s[:60]}")

def test_run_dig_end_to_end(tmp_path):
    from diting.models import Candidate
    cfg = _dig_cfg(tmp_path)
    store = StateStore(str(tmp_path / "state"))
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_dig(cfg, _DigRouter(), store, now_ts=_NOW,
                     search=lambda q: [Candidate("论文A", "http://a", "摘要", "websearch")],
                     fetch=lambda url, *, stealthy=False: "正文内容",
                     feishu_run=fake_feishu)
    assert not report.is_empty() and report.topic == "RAG 新做法"
    assert any("谛听深挖 RAG 新做法" in f for f in os.listdir(cfg.dig_vault_dir))
    assert "argv" in sent                       # 飞书发了短通知
    assert store.is_dug("RAG 新做法")            # 投递成功后才登记

def test_run_dig_no_topic_skips_delivery(tmp_path):
    cfg = _dig_cfg(tmp_path, queue_topics=[])
    store = StateStore(str(tmp_path / "state"))
    store.mark_dug("RAG 新做法")                 # 兴趣里唯一话题也挖过了 → 无题
    sent = {}
    def fake_feishu(argv, **kw):
        sent["argv"] = argv
        class R: returncode = 0
        return R()
    report = run_dig(cfg, _DigRouter(), store, now_ts=_NOW,
                     search=lambda q: [], fetch=lambda u, **k: "", feishu_run=fake_feishu)
    assert report.is_empty()
    assert "argv" not in sent                    # 无题不发飞书
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_dig.py -k run_dig -v`
Expected: FAIL（`ImportError: run_dig`）。

- [ ] **Step 3: 实现 run_dig**

`src/diting/dig.py` 顶部 import 区改为：

```python
from __future__ import annotations
import json
import subprocess
import time
from diting.models import Candidate, DigReport, Interests
from diting.signal.obsidian import collect_session_records
from diting.signal.distill import distill_interests
from diting.signal.dig_topics import select_dig_topic
from diting.sources.fetch import search_engine, fetch_text
from diting.crawl import enrich_bodies
from diting.deliver.dig_out import write_dig_to_vault
from diting.deliver.feishu import send_dig_notice
```

文件末尾追加：

```python
def run_dig(cfg, client, store, *, now_ts=None, search=None, fetch=None,
            feishu_run=subprocess.run) -> DigReport:
    now_ts = now_ts if now_ts is not None else time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    search = search or search_engine
    fetch = fetch or fetch_text
    try:
        signals = collect_session_records(cfg.session_records_dir, cfg.lookback_days, now_ts)
        interests = distill_interests(client, signals) if signals else Interests((), (), (), ())
        topic = select_dig_topic(store, interests, cfg.dig_queue_path)
        if topic is None:
            return DigReport(topic="", date=date, markdown="", one_liner="", source_count=0)
        queries = generate_dig_queries(client, topic)
        seen: set[str] = set()
        cands: list[Candidate] = []
        for q in queries:
            for c in search(q):
                if c.url in seen:
                    continue
                seen.add(c.url)
                cands.append(c)
        cands = cands[:cfg.dig_max_sources]
        cands = enrich_bodies(cands, len(cands), cfg.known_antibot_domains, fetch=fetch)
        report = synthesize_dig(client, topic, date, cands)
    except Exception as e:
        print(f"[谛听 dig] 失败，跳过：{e}")
        return DigReport(topic="", date=date, markdown="", one_liner="", source_count=0)
    if report.is_empty():
        return report
    try:
        path = write_dig_to_vault(report, cfg.dig_vault_dir, now_ts)
        if send_dig_notice(report, cfg.feishu_target, path, run=feishu_run):
            store.mark_dug(report.topic)
    except Exception as e:
        print(f"[谛听 dig] 投递失败，未登记（下次重试）：{e}")
    return report
```

- [ ] **Step 4: CLI 路由**

`src/diting/__main__.py` 的 `if args.cmd == "run":` 分支改为：

```python
    if args.cmd == "run":
        store = StateStore(cfg.state_dir)
        if args.lens == "dig":
            from diting.dig import run_dig
            report = run_dig(cfg, client, store)
            print(f"[dig] {report.date}: " +
                  (f"深挖《{report.topic}》{report.source_count} 篇来源"
                   if not report.is_empty() else "无新题/空，跳过"))
        else:
            report = run_report(args.lens, cfg, client, store)
            print(f"[{report.lens}] {report.date}: {len(report.items)} 条" +
                  ("" if report.items else " — 今天这块没值得看的"))
```

- [ ] **Step 5: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 6: 提交**

```bash
git add src/diting/dig.py src/diting/__main__.py tests/test_dig.py
git commit -m "feat: dig 编排 run_dig（选题→搜→抓→综合→投递→登记）+ CLI 路由"
```

---

### Task 9: launchd 每天 20:00 跑 dig

**Files:**
- Create: `scripts/launchd/ai.diting.dig.plist`
- Modify: `scripts/install-launchd.sh`

**Interfaces:** 无代码接口。产出：`launchctl list | grep diting` 多出 `ai.diting.dig`，每天 20:00 跑 `run-lens.sh dig`。

> 本任务无单测（launchd 是系统配置）。`run-lens.sh` 已是通用的 `run-lens.sh <lens>`，dig 直接复用。

- [ ] **Step 1: 读现有 research plist 作模板**

Run: `cat /Users/<dev-user>/diting-radar/scripts/launchd/ai.diting.research.plist`
观察其结构（Label、ProgramArguments 里 `run-lens.sh research`、StartCalendarInterval 的 Hour、日志路径等）。

- [ ] **Step 2: 创建 dig plist**

复制 research plist 为 `scripts/launchd/ai.diting.dig.plist`，**只改这几处**（其余 research→dig 同步替换，如日志文件名）：
- `Label`：`ai.diting.research` → `ai.diting.dig`
- ProgramArguments 中传给 `run-lens.sh` 的参数：`research` → `dig`
- `StartCalendarInterval`：`Hour` 改为 `20`、`Minute` 为 `0`
- 若 plist 里有日志路径含 `research`（如 `cron-research.log`），改为 `dig`（脚本会写 `cron-dig.log`）

- [ ] **Step 3: 把 dig 纳入安装脚本**

Run: `cat /Users/<dev-user>/diting-radar/scripts/install-launchd.sh`
按它枚举 research/loops/trends 的同款写法，把 `dig` 加进去（通常是 plist 名字列表里加一项 `ai.diting.dig`）。

- [ ] **Step 4: 安装并验证**

```bash
cd /Users/<dev-user>/diting-radar
bash scripts/deploy.sh --restart
launchctl list | grep diting
```
Expected: 列出 4 个任务，含 `ai.diting.dig`。

- [ ] **Step 5: 提交**

```bash
git add scripts/launchd/ai.diting.dig.plist scripts/install-launchd.sh
git commit -m "feat: launchd 每天 20:00 跑 dig 深挖镜头"
```

---

### Task 10: 整合回归 + 真跑验收（控制器自做）

**Files:** 无（验证 + 部署）。

- [ ] **Step 1: 全套测试回归（控制器亲自核实真实数）**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿（阶段一 73 + 阶段二新增约 15 个）。**控制器亲自核实数字**，别只信子代理。

- [ ] **Step 2: 放一个验证话题进想挖清单**

```bash
cd /Users/<dev-user>/diting-radar
printf -- '- "scrapling 反爬最佳实践"\n' > state/dig_queue.yaml
```

- [ ] **Step 3: 真跑 dig 验收**

```bash
bash scripts/run-lens.sh dig
tail -20 state/cron-dig.log
ls -t "$(/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -c 'from diting.config import load_config; print(load_config().dig_vault_dir)')" | head -3
```
Expected: cron-dig.log 显示选到话题、爬到来源、综合成功（且 scrapling 噪音为 0——阶段一已静音）；Obsidian `谛听深挖/` 目录出现 `<date> 谛听深挖 scrapling 反爬最佳实践.md`（reference-manual，含结构化长文）；飞书收到一条 `【谛听 · 🔬 深挖 …】` 短通知。

- [ ] **Step 4: 确认 launchd 四任务**

```bash
launchctl list | grep diting
```
Expected: research / loops / trends / dig 四个都在。

- [ ] **Step 5: 清理验证话题（可选）**

```bash
: > /Users/<dev-user>/diting-radar/state/dig_queue.yaml
```
（dig_queue.yaml 在 gitignore 的 state/ 下，本就不入库。）

---

## Self-Review

**1. Spec 覆盖（阶段二 4.3 节）**
- 选题：清单优先 / 兴趣自动选 / 去重 / 无题 None → Task 3 ✅
- 已挖登记（投递后才登记）→ Task 1（state）+ Task 8（run_dig 投递成功才 mark_dug）✅
- 多角度查询（4-6）→ Task 4 ✅
- 搜 + 深抓正文（top-N 封顶）→ Task 8（search + `enrich_bodies` + `dig_max_sources` cap）✅
- gh 扒代码仓 → **第一版不做**（spec 标可选，已在 Header 声明 YAGNI）
- 综合结构化中文长资料 → Task 5 ✅
- 产出 Obsidian reference-manual 长文 → Task 6 ✅
- 飞书短通知 → Task 7 ✅
- 防失控（每次 1 题 / 来源封顶 / 正文截断）→ Task 8（单题 + cap）+ Task 5（body_limit）✅
- launchd 每天 20:00 → Task 9 ✅
- config 字段（dig_vault_dir / dig_max_sources / dig_queue_path）→ Task 2 ✅
- DigReport 模型 → Task 1 ✅

**2. 占位符扫描**：无 TBD/TODO。Task 9 的"读现有 research plist 作模板"是具体可执行步骤（现有 plist 是确定的模板源），非占位符。

**3. 类型/签名一致性**：
- `DigReport(topic, date, markdown, one_liner, source_count)`（Task 1）↔ Task 5/6/7/8 一致引用。
- `select_dig_topic(store, interests, queue_path)`（Task 3）↔ run_dig 调用一致。
- `generate_dig_queries(client, topic, max_queries=6)`（Task 4）↔ run_dig 调用一致。
- `synthesize_dig(client, topic, date, candidates, *, body_limit=2000)`（Task 5）↔ run_dig 调用一致。
- `write_dig_to_vault(report, dig_vault_dir, now_ts)`（Task 6）↔ run_dig 调用一致。
- `send_dig_notice(report, target, doc_path, *, run)`（Task 7）↔ run_dig 调用一致。
- `StateStore.is_dug/mark_dug`（Task 1）↔ Task 3/Task 8 一致。
- `Config.dig_vault_dir/dig_max_sources/dig_queue_path`（Task 2）↔ run_dig 读 `cfg.*` 一致；run_dig 还读阶段一已有的 `cfg.known_antibot_domains`/`feishu_target`/`session_records_dir`/`lookback_days`。

无遗留问题。
