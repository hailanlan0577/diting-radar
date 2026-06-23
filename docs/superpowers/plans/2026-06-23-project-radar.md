# 谛听 · 项目雷达（per-project 情报）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增第 5 个「项目雷达」镜头，按项目源头记账、只在 STATUS 变更时跑、产出 `谛听项目情报/<slug>.md`，并让 `/<proj>-onboard` 自动读取。

**Architecture:** 复用 `research` 镜头的流水线（distill → generate_queries → run_crawl → enrich → 去重 → judge_novelty → synthesize），但信号只来自单个项目的 STATUS/ONBOARDING、去重用 per-project 表、产出写各项目专属文件。新增 `project_radar.py` 编排 + `project_signal.py`（读状态+算 hash）+ `deliver/project_out.py`（滚动写文件）+ `StateStore`/`Config` 扩展 + 新 launchd。不改现有 4 镜头。

**Tech Stack:** Python 3.11，stdlib（hashlib/sqlite3/json/os/re/time），pytest，DeepSeek（OpenAI 兼容）。无新增 pip 依赖。

## Global Constraints

- **跑测试只用全路径 framework python**：`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`（裸 `python` 被 alias，会跑错解释器）。
- **所有 dataclass 用 `@dataclass(frozen=True)`**（不可变）。
- **precision-first**：合成为空 → 不写文件、不发投递。
- **per-project 去重表 `project_pushed` 与全局 `pushed` 表分开**，互不影响。
- **不改现有 4 镜头 / feishu / 每日情报 / Inbox 写入**。项目雷达是新增第 5 条腿。
- **无新增 pip 依赖**：只用 stdlib。
- **复用现成零件**：`runner.build_sources` / `runner.build_known_context` / `query.generate_queries(lens="research")` / `crawl.run_crawl` / `crawl.enrich_bodies` / `novelty.judge_novelty` / `synthesize.synthesize(lens="research")`。不重写它们。
- **hash 更新规则**：成功处理完一版 STATUS（爬+合成跑通；有料投递成功 / 没料不投递）就更新 hash；任何异常都不更新，留待下次重试。
- **空结果也更新 hash**（这版 STATUS 已处理，别天天重爬）。

---

## File Structure

**新建：**
- `src/diting/signal/project_signal.py` — 读某项目的 STATUS/ONBOARDING 文本 + 算内容 hash（纯 I/O，不碰 store）。
- `src/diting/project_radar.py` — 编排：变更检测 + 单项目流水线 `run_project_radar`。
- `src/diting/deliver/project_out.py` — 把一份 Report 滚动写进 `谛听项目情报/<slug>.md`（最新在最上）。
- `tests/test_project_signal.py` / `tests/test_project_out.py` / `tests/test_project_radar.py`。

**修改：**
- `src/diting/config.py` — 加 `ProjectSpec` + `project_radar_*` 字段 + load。
- `src/diting/state.py` — 加 `project_pushed` 表 + per-project 去重 + STATUS hash 存取。
- `src/diting/novelty.py` — 加 `filter_unpushed_project`。
- `src/diting/__main__.py` — `--lens project` 分支。
- `tests/test_config.py` / `tests/test_state.py` / `tests/test_novelty.py` — 加用例。
- `config.example.yaml` — 加 `project_radar` 示例块。
- `scripts/launchd/ai.diting.project.plist`（新）+ `scripts/install-launchd.sh`（加 project）。
- `~/.claude/skills/<proj>-onboard/SKILL.md` + setup-kit 模板（部署阶段）。

**不动：** `runner.py` / `dig.py` / `query.py` / `crawl.py` / `synthesize.py` / `deliver/obsidian_out.py` / `deliver/feishu.py` / `run-lens.sh`（已通用，`--lens "$1"` 直接支持 `project`）。

---

## Task 1: Config — `project_radar` 配置

**Files:**
- Modify: `src/diting/config.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `ProjectSpec(slug: str, match: str)`（frozen dataclass）；`Config.project_radar_status_dir: str`、`Config.project_radar_output_dir: str`、`Config.project_radar_projects: tuple[ProjectSpec, ...]`（均带默认值，缺省为空）。

- [ ] **Step 1: Write the failing tests**

加到 `tests/test_config.py` 末尾：

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -q`
Expected: FAIL（`ImportError: cannot import name 'ProjectSpec'` / `AttributeError: ... project_radar_status_dir`）。

- [ ] **Step 3: Implement**

在 `src/diting/config.py` 顶部（`@dataclass(frozen=True) class Config` 之前）加：

```python
@dataclass(frozen=True)
class ProjectSpec:
    slug: str
    match: str
```

在 `Config` 末尾（`extra_lookback_days` 之后）加三个字段：

```python
    project_radar_status_dir: str = ""
    project_radar_output_dir: str = ""
    project_radar_projects: tuple[ProjectSpec, ...] = ()
```

在 `load_config` 的 `Config(...)` 构造里（`extra_lookback_days=...,` 之后）加：

```python
            project_radar_status_dir=(raw.get("project_radar") or {}).get("status_dir", ""),
            project_radar_output_dir=(raw.get("project_radar") or {}).get("output_dir", ""),
            project_radar_projects=tuple(
                ProjectSpec(slug=str(p["slug"]), match=str(p["match"]))
                for p in ((raw.get("project_radar") or {}).get("projects", []) or [])
            ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -q`
Expected: PASS（全绿）。

- [ ] **Step 5: Commit**

```bash
git add src/diting/config.py tests/test_config.py
git commit -m "feat: config 增加 project_radar（ProjectSpec + status_dir/output_dir/projects）"
```

---

## Task 2: StateStore — per-project 去重 + STATUS hash

**Files:**
- Modify: `src/diting/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `StateStore.is_project_pushed(slug: str, url: str) -> bool`、`mark_project_pushed(slug, url) -> None`、`get_status_hash(slug: str) -> str | None`、`set_status_hash(slug: str, h: str) -> None`。
- 存储：`project_pushed(slug, url)` 表在 `pushed.db`；STATUS hash 在 `state/project_radar.json`（`{slug: hash}`）。

- [ ] **Step 1: Write the failing tests**

加到 `tests/test_state.py` 末尾：

```python
def test_project_pushed_dedup_is_per_slug(tmp_path):
    s = StateStore(str(tmp_path / "state"))
    assert s.is_project_pushed("ytst", "http://a") is False
    s.mark_project_pushed("ytst", "http://a")
    assert s.is_project_pushed("ytst", "http://a") is True
    # 不同项目同 url 互不影响（项目流要完整）
    assert s.is_project_pushed("lbc", "http://a") is False
    # 与全局 pushed 表分开
    assert s.is_pushed("http://a") is False


def test_status_hash_roundtrip(tmp_path):
    s = StateStore(str(tmp_path / "state"))
    assert s.get_status_hash("ytst") is None
    s.set_status_hash("ytst", "abc123")
    assert s.get_status_hash("ytst") == "abc123"
    # 持久化：换实例仍记得
    s2 = StateStore(str(tmp_path / "state"))
    assert s2.get_status_hash("ytst") == "abc123"
    s2.set_status_hash("ytst", "def456")
    assert s2.get_status_hash("ytst") == "def456"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_state.py -q`
Expected: FAIL（`AttributeError: 'StateStore' object has no attribute 'is_project_pushed'`）。

- [ ] **Step 3: Implement**

在 `StateStore.__init__` 里，`self._dug = ...` 之后加一行 json 路径：

```python
        self._proj = os.path.join(self.dir, "project_radar.json")
```

在 `__init__` 的 `with sqlite3.connect(self._db) as c:` 块里，已有的 `CREATE TABLE ... pushed` 之后加一行建表：

```python
            c.execute("CREATE TABLE IF NOT EXISTS project_pushed "
                      "(slug TEXT, url TEXT, PRIMARY KEY (slug, url))")
```

在类末尾（`mark_dug` 之后）加方法：

```python
    def is_project_pushed(self, slug: str, url: str) -> bool:
        with sqlite3.connect(self._db) as c:
            return c.execute("SELECT 1 FROM project_pushed WHERE slug=? AND url=?",
                             (slug, url)).fetchone() is not None

    def mark_project_pushed(self, slug: str, url: str) -> None:
        with sqlite3.connect(self._db) as c:
            c.execute("INSERT OR IGNORE INTO project_pushed (slug, url) VALUES (?, ?)",
                      (slug, url))

    def _load_proj_hashes(self) -> dict[str, str]:
        if not os.path.exists(self._proj):
            return {}
        try:
            with open(self._proj, "r", encoding="utf-8") as f:
                return json.load(f) or {}
        except (json.JSONDecodeError, OSError):
            return {}

    def get_status_hash(self, slug: str) -> str | None:
        return self._load_proj_hashes().get(slug)

    def set_status_hash(self, slug: str, h: str) -> None:
        data = self._load_proj_hashes()
        data[slug] = h
        try:
            with open(self._proj, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except OSError as e:
            print(f"[谛听] 写 project_radar.json 失败：{e}")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_state.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/diting/state.py tests/test_state.py
git commit -m "feat: StateStore 增加 per-project 去重表 + STATUS hash 存取"
```

---

## Task 3: project_signal — 读项目状态文本 + 算 hash

**Files:**
- Create: `src/diting/signal/project_signal.py`
- Test: `tests/test_project_signal.py`

**Interfaces:**
- Produces: `read_status_text(status_dir: str, match: str) -> str`（按文件名子串 match 找 `.md`，按文件名排序后拼正文；目录/文件读不到返 `""`）；`status_hash(text: str) -> str`（sha256 十六进制）。

- [ ] **Step 1: Write the failing tests**

新建 `tests/test_project_signal.py`：

```python
from diting.signal.project_signal import read_status_text, status_hash


def test_read_status_text_matches_and_concats(tmp_path):
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态正文", encoding="utf-8")
    (d / "macbook-ytst-ONBOARDING.md").write_text("ytst 交接正文", encoding="utf-8")
    (d / "macbook-lbc-STATUS.md").write_text("别的项目", encoding="utf-8")
    (d / "ignore.txt").write_text("非 md", encoding="utf-8")
    text = read_status_text(str(d), "ytst")
    assert "ytst 状态正文" in text
    assert "ytst 交接正文" in text
    assert "别的项目" not in text          # 不匹配的项目不进来
    assert "非 md" not in text             # 非 .md 不读
    # 文件名作为标题带进去（含话题，对蒸馏有用）
    assert "macbook-ytst-STATUS" in text


def test_read_status_text_missing_dir_returns_empty(tmp_path):
    assert read_status_text(str(tmp_path / "nope"), "ytst") == ""


def test_read_status_text_no_match_returns_empty(tmp_path):
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-lbc-STATUS.md").write_text("x", encoding="utf-8")
    assert read_status_text(str(d), "ytst") == ""


def test_status_hash_stable_and_sensitive():
    assert status_hash("abc") == status_hash("abc")     # 同内容同 hash
    assert status_hash("abc") != status_hash("abd")     # 内容变 hash 变
    assert len(status_hash("abc")) == 64                 # sha256 十六进制
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_signal.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'diting.signal.project_signal'`）。

- [ ] **Step 3: Implement**

新建 `src/diting/signal/project_signal.py`：

```python
"""项目雷达信号：读单个项目的 STATUS/ONBOARDING 文本 + 算内容 hash。"""
from __future__ import annotations
import hashlib
import os


def read_status_text(status_dir: str, match: str) -> str:
    """读 status_dir 下文件名含 match 的所有 .md，按文件名排序拼接。

    每篇前面带文件名（含项目名/话题，对蒸馏有用）。目录不存在/不可读 → 返 ""。
    """
    try:
        names = sorted(n for n in os.listdir(status_dir)
                       if n.endswith(".md") and match in n)
    except OSError:
        return ""
    parts: list[str] = []
    for name in names:
        try:
            with open(os.path.join(status_dir, name), "r", encoding="utf-8") as f:
                content = f.read()
        except OSError:
            continue
        parts.append(f"《{name[:-3]}》\n{content}")
    return "\n\n---\n\n".join(parts)


def status_hash(text: str) -> str:
    """内容 hash（sha256 十六进制）——用于判断某项目 STATUS 是否变了。"""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_signal.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/diting/signal/project_signal.py tests/test_project_signal.py
git commit -m "feat: project_signal 读项目 STATUS/ONBOARDING 文本 + 算 hash"
```

---

## Task 4: novelty — per-project 去重过滤

**Files:**
- Modify: `src/diting/novelty.py`
- Test: `tests/test_novelty.py`

**Interfaces:**
- Consumes: `Candidate`（`models.py`，字段 `title,url,summary,source,body`）；`StateStore.is_project_pushed(slug, url)`（Task 2）。
- Produces: `filter_unpushed_project(candidates: list[Candidate], store, slug: str) -> list[Candidate]`。

- [ ] **Step 1: Write the failing test**

加到 `tests/test_novelty.py` 末尾：

```python
def test_filter_unpushed_project_is_per_slug(tmp_path):
    from diting.novelty import filter_unpushed_project
    from diting.models import Candidate
    from diting.state import StateStore
    store = StateStore(str(tmp_path / "state"))
    store.mark_project_pushed("ytst", "http://a")
    cands = [Candidate("A", "http://a", "", "websearch"),
             Candidate("B", "http://b", "", "websearch")]
    # ytst 已推过 a → 只剩 b
    assert [c.url for c in filter_unpushed_project(cands, store, "ytst")] == ["http://b"]
    # 别的项目没推过 a → a 仍保留（项目流互不影响）
    assert [c.url for c in filter_unpushed_project(cands, store, "lbc")] == ["http://a", "http://b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_novelty.py::test_filter_unpushed_project_is_per_slug -q`
Expected: FAIL（`ImportError: cannot import name 'filter_unpushed_project'`）。

- [ ] **Step 3: Implement**

在 `src/diting/novelty.py` 的 `filter_unpushed` 之后加：

```python
def filter_unpushed_project(candidates: list[Candidate], store, slug: str) -> list[Candidate]:
    return [c for c in candidates if not store.is_project_pushed(slug, c.url)]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_novelty.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/diting/novelty.py tests/test_novelty.py
git commit -m "feat: novelty 增加 per-project 去重过滤 filter_unpushed_project"
```

---

## Task 5: project_out — 滚动写项目情报文件

**Files:**
- Create: `src/diting/deliver/project_out.py`
- Test: `tests/test_project_out.py`

**Interfaces:**
- Consumes: `Report`（`models.py`，字段 `lens,date,items,notes`；`items` 是 `RankedItem` 元组，字段 `title,url,one_liner,why_it_matters,source,lens`）。
- Produces: `write_project_intel(slug: str, report: Report, output_dir: str) -> str`（返回写入路径 `output_dir/<slug>.md`；首次建带 frontmatter，之后把新日期小节插到最上、更新 `last_updated`）。

- [ ] **Step 1: Write the failing tests**

新建 `tests/test_project_out.py`：

```python
from diting.models import Report, RankedItem
from diting.deliver.project_out import write_project_intel


def _report(date, items):
    ranked = tuple(RankedItem(title=t, url=u, one_liner="", why_it_matters=w,
                              source="websearch", lens="research") for t, u, w in items)
    return Report(lens="research", date=date, items=ranked, notes=())


def test_write_creates_with_frontmatter(tmp_path):
    out = str(tmp_path / "谛听项目情报")
    r = _report("2026-06-23", [("论文A", "http://a", "对 ytst 精排有用")])
    path = write_project_intel("ytst", r, out)
    assert path.endswith("ytst.md")
    text = open(path, encoding="utf-8").read()
    assert "type: progress-log" in text
    assert "title: 谛听项目情报 · ytst" in text
    assert "last_updated: 2026-06-23" in text
    assert "## 2026-06-23" in text
    assert "- [论文A](http://a) — 对 ytst 精排有用" in text


def test_write_prepends_newest_on_top(tmp_path):
    out = str(tmp_path / "谛听项目情报")
    write_project_intel("ytst", _report("2026-06-20", [("旧", "http://old", "旧理由")]), out)
    path = write_project_intel("ytst", _report("2026-06-23", [("新", "http://new", "新理由")]), out)
    text = open(path, encoding="utf-8").read()
    # 新日期小节在旧日期小节之上
    assert text.index("## 2026-06-23") < text.index("## 2026-06-20")
    # frontmatter 只有一份（title 只出现一次），last_updated 更到最新
    assert text.count("title: 谛听项目情报 · ytst") == 1
    assert "last_updated: 2026-06-23" in text
    assert "last_updated: 2026-06-20" not in text
    assert "- [新](http://new) — 新理由" in text
    assert "- [旧](http://old) — 旧理由" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_out.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'diting.deliver.project_out'`）。

- [ ] **Step 3: Implement**

新建 `src/diting/deliver/project_out.py`：

```python
# src/diting/deliver/project_out.py
from __future__ import annotations
import os
import re
from diting.models import Report


def _header(slug: str, date: str) -> str:
    return (f"---\ntitle: 谛听项目情报 · {slug}\ntype: progress-log\n"
            f"status: active\ncreated: {date}\nlast_updated: {date}\n---\n\n"
            f"# 谛听项目情报 · {slug}\n\n"
            f"> 谛听「项目雷达」镜头自动产出 · 只收和本项目直接相关的料 · 最新在最上\n\n")


def _section(report: Report) -> str:
    lines = [f"## {report.date}"]
    for it in report.items:
        lines.append(f"- [{it.title}]({it.url}) — {it.why_it_matters}")
    return "\n".join(lines) + "\n"


def write_project_intel(slug: str, report: Report, output_dir: str) -> str:
    """把一份 Report 滚动写进 output_dir/<slug>.md（最新日期小节在最上）。"""
    os.makedirs(output_dir, exist_ok=True)
    path = os.path.join(output_dir, f"{slug}.md")
    section = _section(report)
    if not os.path.exists(path):
        content = _header(slug, report.date) + section
    else:
        with open(path, "r", encoding="utf-8") as f:
            old = f.read()
        old = re.sub(r"(?m)^last_updated: .*$", f"last_updated: {report.date}", old, count=1)
        idx = old.find("\n## ")
        if idx == -1:
            content = old.rstrip() + "\n\n" + section
        else:
            content = old[:idx + 1] + section + "\n" + old[idx + 1:]
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    return path
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_out.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/diting/deliver/project_out.py tests/test_project_out.py
git commit -m "feat: project_out 滚动写 谛听项目情报/<slug>.md（最新在最上）"
```

---

## Task 6: project_radar — 变更检测 `detect_changed_projects`

**Files:**
- Create: `src/diting/project_radar.py`
- Test: `tests/test_project_radar.py`

**Interfaces:**
- Consumes: `Config.project_radar_status_dir` / `project_radar_projects`（Task 1）；`read_status_text` / `status_hash`（Task 3）；`StateStore.get_status_hash`（Task 2）。
- Produces: `detect_changed_projects(cfg, store) -> list[tuple[str, str, str]]`，返回 `(slug, text, hash)` 列表——只含 STATUS 有内容且 hash 与上次不同（含从没跑过）的项目。

- [ ] **Step 1: Write the failing test**

新建 `tests/test_project_radar.py`：

```python
import types
import time
from diting.config import ProjectSpec
from diting.state import StateStore

_NOW = time.mktime(time.strptime("2026-06-23 11:00", "%Y-%m-%d %H:%M"))


def _radar_cfg(status_dir, out_dir, projects):
    return types.SimpleNamespace(
        project_radar_status_dir=str(status_dir),
        project_radar_output_dir=str(out_dir),
        project_radar_projects=projects,
        fetch_top_n=5, known_antibot_domains=(),
    )


def test_detect_changed_projects(tmp_path):
    from diting.project_radar import detect_changed_projects
    d = tmp_path / "ps"; d.mkdir()
    f = d / "macbook-ytst-STATUS.md"
    f.write_text("ytst v1", encoding="utf-8")
    cfg = _radar_cfg(d, tmp_path / "out", (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))

    # 从没跑过 → 入选
    changed = detect_changed_projects(cfg, store)
    assert [c[0] for c in changed] == ["ytst"]
    slug, text, h = changed[0]
    assert "ytst v1" in text

    # 记下 hash 后再检测 → 不入选
    store.set_status_hash(slug, h)
    assert detect_changed_projects(cfg, store) == []

    # STATUS 内容变了 → 又入选
    f.write_text("ytst v2 改了", encoding="utf-8")
    assert [c[0] for c in detect_changed_projects(cfg, store)] == ["ytst"]


def test_detect_skips_project_without_status_file(tmp_path):
    from diting.project_radar import detect_changed_projects
    d = tmp_path / "ps"; d.mkdir()  # 空目录，没有任何 STATUS
    cfg = _radar_cfg(d, tmp_path / "out", (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    assert detect_changed_projects(cfg, store) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_radar.py -q`
Expected: FAIL（`ModuleNotFoundError: No module named 'diting.project_radar'`）。

- [ ] **Step 3: Implement**

新建 `src/diting/project_radar.py`（本任务只写 `detect_changed_projects` + 它需要的 import；Task 7 再补其余 import 和 `run_project_radar`）：

```python
# src/diting/project_radar.py
from __future__ import annotations
from diting.signal.project_signal import read_status_text, status_hash


def detect_changed_projects(cfg, store) -> list[tuple[str, str, str]]:
    """返回 STATUS 变更（或从没跑过）的项目 (slug, text, hash)。无 STATUS 文件的跳过。"""
    out: list[tuple[str, str, str]] = []
    for spec in cfg.project_radar_projects:
        text = read_status_text(cfg.project_radar_status_dir, spec.match)
        if not text:
            continue
        h = status_hash(text)
        if h != store.get_status_hash(spec.slug):
            out.append((spec.slug, text, h))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_radar.py -q`
Expected: PASS。

- [ ] **Step 5: Commit**

```bash
git add src/diting/project_radar.py tests/test_project_radar.py
git commit -m "feat: project_radar 变更检测 detect_changed_projects"
```

---

## Task 7: project_radar — 端到端 `run_project_radar` + CLI 接入

**Files:**
- Modify: `src/diting/project_radar.py`
- Modify: `src/diting/__main__.py`
- Test: `tests/test_project_radar.py`

**Interfaces:**
- Consumes: Task 6 的 `detect_changed_projects`；Task 1-5 的全部产物；`runner.build_sources` / `build_known_context`。
- Produces: `run_project_radar(cfg, client, store, *, now_ts=None, sources=None, enrich=enrich_bodies) -> list[Report]`。
- 行为：对每个变更项目跑 research 流水线；非空报告 → 写文件 + `mark_project_pushed` 每条；成功处理（含空结果）→ `set_status_hash`；异常 → 跳过、不更新 hash。

- [ ] **Step 1: Write the failing tests**

加到 `tests/test_project_radar.py` 末尾（`_Router` 按 system prompt 关键词路由各步）：

```python
from diting.models import Candidate


class _Router:
    """按 system prompt 关键词模拟 DeepSeek 各步。"""
    def complete_json(self, messages, **kw):
        s = messages[0]["content"]
        if "提炼" in s:                      # distill
            return {"topics": ["以图搜图 精排"], "entities": [], "open_loops": [], "decisions": []}
        if "科研雷达" in s:                  # generate_queries(lens=research)
            return {"queries": ["image retrieval rerank"]}
        if "对他是新的" in s:                # judge_novelty
            return {"novel_urls": ["http://a"]}
        if "私人技术情报员" in s:            # synthesize(lens=research)
            return {"items": [{"url": "http://a", "title": "论文A",
                               "one_liner": "x", "why_it_matters": "对 ytst 精排有用"}]}
        raise ValueError(f"unexpected prompt: {s[:40]}")


def test_run_project_radar_end_to_end(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 在做以图搜图精排", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    reports = run_project_radar(
        cfg, _Router(), store, now_ts=_NOW,
        sources={"websearch": lambda q: [Candidate("论文A", "http://a", "摘要", "websearch")]},
        enrich=lambda cands, *a, **k: cands,
    )
    assert len(reports) == 1 and not reports[0].is_empty()
    text = (out / "ytst.md").read_text(encoding="utf-8")
    assert "[论文A](http://a) — 对 ytst 精排有用" in text
    assert store.is_project_pushed("ytst", "http://a")   # 投递成功后登记
    assert store.get_status_hash("ytst") is not None      # hash 更新


def test_run_project_radar_skips_unchanged(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))
    # 第一次正常跑（用真 router）
    run_project_radar(cfg, _Router(), store, now_ts=_NOW,
                      sources={"websearch": lambda q: [Candidate("A", "http://a", "", "websearch")]},
                      enrich=lambda c, *a, **k: c)

    class _Boom:
        def complete_json(self, *a, **k):
            raise AssertionError("STATUS 没变不该再调模型")
    # STATUS 没变 → detect 返空 → 模型一次都不调
    reports = run_project_radar(cfg, _Boom(), store, now_ts=_NOW,
                                sources={"websearch": lambda q: []},
                                enrich=lambda c, *a, **k: c)
    assert reports == []


def test_run_project_radar_empty_updates_hash_no_file(tmp_path):
    from diting.project_radar import run_project_radar
    d = tmp_path / "ps"; d.mkdir()
    (d / "macbook-ytst-STATUS.md").write_text("ytst 状态", encoding="utf-8")
    out = tmp_path / "out"
    cfg = _radar_cfg(d, out, (ProjectSpec("ytst", "ytst"),))
    store = StateStore(str(tmp_path / "state"))

    class _Empty(_Router):
        def complete_json(self, messages, **kw):
            s = messages[0]["content"]
            if "对他是新的" in s:
                return {"novel_urls": []}          # 全判为旧 → 候选清零 → 空报告
            return super().complete_json(messages, **kw)

    reports = run_project_radar(cfg, _Empty(), store, now_ts=_NOW,
                                sources={"websearch": lambda q: [Candidate("A", "http://a", "", "websearch")]},
                                enrich=lambda c, *a, **k: c)
    assert len(reports) == 1 and reports[0].is_empty()
    assert not (out / "ytst.md").exists()           # 空 → 不写文件
    assert store.get_status_hash("ytst") is not None  # 但 hash 更新（别天天重爬）
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_radar.py -q`
Expected: FAIL（`ImportError: cannot import name 'run_project_radar'`）。

- [ ] **Step 3: Implement `run_project_radar`**

先在 `src/diting/project_radar.py` 顶部 import 区（现有那行 `from diting.signal.project_signal import ...` 之后）补上本函数要用的 import：

```python
import time
from diting.models import SignalItem, Report
from diting.signal.distill import distill_interests
from diting.query import generate_queries
from diting.crawl import run_crawl, enrich_bodies
from diting.novelty import filter_unpushed_project, judge_novelty
from diting.synthesize import synthesize
from diting.deliver.project_out import write_project_intel
from diting.runner import build_sources, build_known_context
```

再在文件末尾（`detect_changed_projects` 之后）加：

```python
def run_project_radar(cfg, client, store, *, now_ts=None, sources=None,
                      enrich=enrich_bodies) -> list[Report]:
    """对每个 STATUS 变更的项目跑一遍 research 流水线，产出该项目专属情报。

    成功处理完一版 STATUS（含空结果）→ 更新 hash；异常 → 不更新、下次重试。
    """
    now_ts = now_ts if now_ts is not None else time.time()
    date = time.strftime("%Y-%m-%d", time.localtime(now_ts))
    reports: list[Report] = []
    for slug, text, h in detect_changed_projects(cfg, store):
        try:
            interests = distill_interests(client, [SignalItem("project_status", text, now_ts)])
            profile = store.load_profile()
            queries = generate_queries(client, "research", interests, profile)
            candidates, _notes = run_crawl(queries, sources or build_sources(cfg))
            candidates = enrich(candidates, cfg.fetch_top_n, cfg.known_antibot_domains)
            candidates = filter_unpushed_project(candidates, store, slug)
            candidates = judge_novelty(client, candidates, build_known_context(interests, profile))
            report = synthesize(client, "research", date, candidates, interests, [])
        except Exception as e:
            print(f"[谛听 project] {slug} 失败，跳过（hash 不更新，下次重试）：{e}")
            continue
        delivered = True
        if not report.is_empty():
            try:
                write_project_intel(slug, report, cfg.project_radar_output_dir)
                for it in report.items:
                    store.mark_project_pushed(slug, it.url)
            except Exception as e:
                print(f"[谛听 project] {slug} 投递失败，未更新 hash（下次重试）：{e}")
                delivered = False
        if delivered:
            store.set_status_hash(slug, h)
        reports.append(report)
    return reports
```

> 注：项目雷达第一版**不发飞书**，只写 Obsidian——onboard 时才读。所以不带 `feishu_run` 参数（YAGNI）。日后若要加飞书短通知再补。

- [ ] **Step 4: Wire CLI in `__main__.py`**

把 `src/diting/__main__.py` 里 `if args.lens == "dig":` 这段改成加一个 `elif`（在 `else: run_report` 之前）：

```python
        if args.lens == "dig":
            from diting.dig import run_dig
            report = run_dig(cfg, client, store)
            print(f"[dig] {report.date}: " +
                  (f"深挖《{report.topic}》{report.source_count} 篇来源"
                   if not report.is_empty() else "无新题/空，跳过"))
        elif args.lens == "project":
            from diting.project_radar import run_project_radar
            reports = run_project_radar(cfg, client, store)
            n = sum(1 for r in reports if not r.is_empty())
            print(f"[project] 跑了 {len(reports)} 个变更项目，{n} 个产出情报")
        else:
            report = run_report(args.lens, cfg, client, store)
            print(f"[{report.lens}] {report.date}: {len(report.items)} 条" +
                  ("" if report.items else " — 今天这块没值得看的"))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_project_radar.py -q`
Expected: PASS（3 个端到端用例全绿）。

- [ ] **Step 6: Run the FULL suite（控制器亲自核实真实数，别只信单文件）**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 原有 91 测试 + 本计划新增用例全 PASS，0 失败。

- [ ] **Step 7: Commit**

```bash
git add src/diting/project_radar.py src/diting/__main__.py tests/test_project_radar.py
git commit -m "feat: run_project_radar 端到端 + CLI --lens project"
```

---

## Task 8: 配置示例 + vault 目录登记

**Files:**
- Modify: `config.example.yaml`
- Manual（vault，仓库外）: vault 根 `README.md`

- [ ] **Step 1: 在 `config.example.yaml` 末尾（`state_dir:` 那行之后）追加**

```yaml
# 项目雷达（第 5 镜头）：按项目源头记账。只在某项目 STATUS 变更时给它跑一遍，
# 产出写 output_dir/<slug>.md，供 /<slug>-onboard 自动读。projects 同时是参与白名单。
project_radar:
  status_dir: "/Users/<run-user>/project-status"   # 各项目 STATUS/ONBOARDING 汇集（statussync 推来）
  output_dir: "/Users/<dev-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/谛听项目情报"
  projects:
    - {slug: "ytst", match: "ytst"}                       # slug = onboard 缩写 = 情报文件名
    - {slug: "lbc",  match: "luxury-bag-copilot"}         # match = 在 status_dir 里找文件用的子串
    # …按需增减；漏配某项目 = 它没有项目雷达（不报错）
```

- [ ] **Step 2: 登记 vault 新一级目录（手动，仓库外）**

谛听首次写入会自动建 `谛听项目情报/` 目录。按 Obsidian 文档纪律，在 vault 根 `README.md` 的「📁 一级目录」表加一行：

```markdown
| 谛听项目情报/ | 谛听「项目雷达」镜头按项目产出的专属情报流（每项目一份，最新在最上） |
```

- [ ] **Step 3: Commit（仅 config 示例；README 在 vault 不入 git）**

```bash
git add config.example.yaml
git commit -m "docs: config.example 增加 project_radar 示例块"
```

---

## Task 9: 新增 launchd 定时 + 部署到 Mac Studio

> 本任务无单元测试，验证 = 手动 kickstart 后看日志 + vault 文件。

**Files:**
- Create: `scripts/launchd/ai.diting.project.plist`
- Modify: `scripts/install-launchd.sh`

- [ ] **Step 1: 新建 `scripts/launchd/ai.diting.project.plist`**

镜像 `ai.diting.research.plist`，改 Label / lens 参数 / 时段（11:00，research 之后）：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>ai.diting.project</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/bash</string>
    <string>/Users/<dev-user>/diting-radar/scripts/run-lens.sh</string>
    <string>project</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict>
    <key>Hour</key>
    <integer>11</integer>
    <key>Minute</key>
    <integer>0</integer>
  </dict>
  <key>StandardErrorPath</key>
  <string>/Users/<dev-user>/diting-radar/state/launchd-project.err</string>
</dict>
</plist>
```

> ⚠️ **Mac Studio 路径是 `/Users/<run-user>`**：和现有 5 个 plist 一样，部署到 Studio 时这个 plist 的两处路径要改成 `/Users/<run-user>/...`（用户/Claude 在 Studio 上按既有方式处理）。

- [ ] **Step 2: 改 `scripts/install-launchd.sh`**

把 `LENSES=(research loops trends dig)` 改为：

```bash
LENSES=(research loops trends dig project)
```

并在 `cp "$PLIST_DIR/ai.diting.dig.plist" "$LAUNCH_AGENTS_DIR/"` 那行之后加一行：

```bash
cp "$PLIST_DIR/ai.diting.project.plist"  "$LAUNCH_AGENTS_DIR/"
```

- [ ] **Step 3: Commit**

```bash
git add scripts/launchd/ai.diting.project.plist scripts/install-launchd.sh
git commit -m "feat: launchd 增加 ai.diting.project（每天 11:00 跑项目雷达）"
```

- [ ] **Step 4: 部署到 Mac Studio（参照 CLAUDE.md「部署工作流」）**

```bash
# MacBook：先确认全绿 + push
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
git push -u origin feat/project-radar    # 或合并到 main 后 push（按用户意愿）
# 同步代码（⚠️ 别让 run-lens.sh / 定制 plist 被 MacBook 版覆盖；同步后在 Studio 确认）
rsync -av --exclude '.venv' --exclude 'state/cron-*.log' src/ scripts/ pyproject.toml macstudio:~/diting-radar/
# Studio：改 ai.diting.project.plist 两处路径为 /Users/<run-user>，再装 launchd
ssh macstudio 'cd ~/diting-radar && bash scripts/install-launchd.sh'
# Studio：在 config.yaml 加 project_radar 块（status_dir/output_dir 用 <run-user> 真路径 + projects 真表）
```

- [ ] **Step 5: 手动触发验证**

```bash
ssh macstudio 'launchctl kickstart -k gui/$(id -u)/ai.diting.project; sleep 2; tail -20 ~/diting-radar/state/cron-project.log'
# 确认：日志打印 "[project] 跑了 N 个变更项目，M 个产出情报"
# 确认：vault 里出现 谛听项目情报/<slug>.md（对有新料的项目）
ssh macstudio 'launchctl list | grep diting'   # 应有 6 个：4 镜头 + prefetch + project
```

---

## Task 10: onboard 接入（各项目 skill + setup-kit 模板）

> 无单元测试，验证 = 跑一次 `/<proj>-onboard` 看是否汇报项目情报。

**Files（仓库外，全局 skill）:**
- Modify: `~/.claude/skills/<proj>-onboard/SKILL.md`（先改 config.projects 里列的活跃项目）
- Modify: `~/.claude/skills/setup-kit/`（+ `setup-kit-pro`）的 onboard 模板

- [ ] **Step 1: 给每个 `<proj>-onboard/SKILL.md` 加一步**

在现有「扫 Obsidian 最近相关文档」步骤**之后**插入下面这步（把 `<slug>` 换成该项目 slug，如 ytst）：

```markdown
### 第 3.5 步：读谛听项目情报（v0.4.0 新增）

谛听「项目雷达」镜头会把和本项目直接相关的情报滚动写进
`谛听项目情报/<slug>.md`（最新在最上）。**读它最上面前 2 个日期小节**（约最近 2 周），
把"谛听最近替本项目盯到的料"并进第 4 步汇报。

- 用 Read tool 读 `<Obsidian vault>/谛听项目情报/<slug>.md`（只看顶部最近 2 节，别读整篇旧档）。
- **文件不存在** → 跳过本步，汇报"暂无谛听项目情报"。
- 汇报格式：单列一节「🛰️ 谛听最近盯到（项目雷达）」+ 每条标题+为何重要。
```

并把第 4 步汇报结构里加一节「🛰️ 谛听最近盯到」。

- [ ] **Step 2: 同步改 setup-kit / setup-kit-pro 的 onboard 模板**

在 `~/.claude/skills/setup-kit/`（及 `setup-kit-pro/`）的 onboard 模板里加同样的「读谛听项目情报」步（用模板占位符 `{slug}` / `{vault}`），让以后 `/setup-kit` 新建的项目自带此步。

- [ ] **Step 3: 手动验证**

对一个 config 里配了、且已有 `谛听项目情报/<slug>.md` 的项目跑一次 onboard（如 `/ytst-onboard`），确认它汇报里出现「🛰️ 谛听最近盯到」一节；对没有该文件的项目确认它平稳跳过、汇报"暂无"。

---

## Self-Review（写完计划后对照 spec 自检）

**1. Spec coverage：**
- §3「新增项目雷达镜头」→ Task 6+7 ✅
- §4.1 变更检测 → Task 6 ✅ ；§4.2 项目信号 → Task 3 ✅ ；§4.3 编排 → Task 7 ✅ ；§4.4 投递 → Task 5 ✅ ；§4.5 state 扩展 → Task 2 ✅
- §5 项目名映射（ProjectSpec slug/match + config 表）→ Task 1 ✅
- §6 per-project 去重（project_pushed 独立表）→ Task 2 + Task 4 ✅
- §7 输出文件格式（frontmatter + 最新在最上 + 空不写）→ Task 5 ✅
- §8 onboard 接入 + setup-kit → Task 10 ✅
- §9 定时（新 launchd 11:00；run-lens.sh 已通用无需改）→ Task 9 ✅
- §10 错误处理 + hash 更新规则（空也更新、异常不更新）→ Task 7 用例 ✅
- §11 测试计划 → 各任务 TDD 覆盖 ✅
- §12 影响文件清单 → File Structure + 各任务 Files ✅

**2. Placeholder 扫描：** 无 TBD/TODO；每个 code step 都有完整代码；`feishu_run` 参数有明确说明（接口占位，第一版不发飞书）。✅

**3. 类型/命名一致性：**
- `ProjectSpec(slug, match)` 在 Task 1 定义，Task 6/7 测试一致引用 ✅
- `is_project_pushed/mark_project_pushed/get_status_hash/set_status_hash` Task 2 定义，Task 4/6/7 一致使用 ✅
- `read_status_text/status_hash` Task 3 定义，Task 6 使用 ✅
- `filter_unpushed_project` Task 4 定义，Task 7 使用 ✅
- `write_project_intel(slug, report, output_dir)` Task 5 定义，Task 7 调用签名一致（不带 now_ts）✅
- `run_project_radar(...)` / `detect_changed_projects(cfg, store)` Task 6/7 一致 ✅
- 复用函数签名与现有代码核对：`generate_queries(client, "research", interests, profile)` / `run_crawl(queries, sources)` / `enrich_bodies(cands, top_n, antibot)` / `judge_novelty(client, cands, ctx)` / `synthesize(client, "research", date, cands, interests, notes)` / `build_sources(cfg)` / `build_known_context(interests, profile)` 全部与读到的源码一致 ✅

---

## Execution Handoff

依赖顺序：Task 1 → 2 → 3 → 4 → 5 → 6 → 7（代码，TDD，逐个 commit）→ 8（配置）→ 9（部署）→ 10（onboard 接入）。
Task 1-5 互相独立（只依赖各自已有模块），可并行；Task 6 依赖 1/2/3，Task 7 依赖全部；Task 9/10 在代码合入后做。

