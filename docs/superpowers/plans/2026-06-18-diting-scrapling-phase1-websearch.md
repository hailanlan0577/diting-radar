# 谛听 阶段一：scrapling 抓取内核 + 日常网搜增强 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 给谛听补一个共用的 scrapling 抓取内核，并用它把日常 research/loops 镜头的网搜修强——searxng 空了能兜底搜，候选能真读正文喂大模型。

**Architecture:** 新增 `sources/fetch.py` 抓取内核（`fetch_text` 读正文、`search_engine` 兜底搜索，均失败返空/[]、绝不抛出）。`websearch.py` 在 searxng 返空时 fallback 到 `search_engine`。`crawl.py` 新增 `enrich_bodies` 对去重后 top-N 候选抓正文填入 `Candidate.body`，`novelty`/`synthesize` 在有正文时优先用正文判断。

**Tech Stack:** Python 3.11、scrapling（抓取/抗反爬）、trafilatura（正文抽取，已装）、httpx（已装）、pytest。

> 本计划只覆盖**阶段一**（抓取内核 + 日常网搜增强），交付后日常情报即变强、可独立验证。阶段二「dig 自动深挖镜头」依赖本阶段的抓取内核，待本阶段验证后另起计划。设计依据：`docs/superpowers/specs/2026-06-18-diting-scrapling-deepdig-design.md`。

## Global Constraints

- **跑 Python 一律用 framework python 全路径**：`/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`（本机 `python` 被 alias 到别处）。测试命令统一 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest`。
- **绝不裸用 `python` / `pip`**；装包用 `…/python3 -m pip`。
- **不可变数据**：`models.py` 全是 `@dataclass(frozen=True)`；改字段值用 `dataclasses.replace`，不原地改。
- **precision-first / 绝不抛出**：抓取内核任何失败（网络、解析、反爬）一律返回 `""` 或 `[]`，由调用方据空跳过——宁缺毋滥。
- **反爬不调真 Chrome**：反爬站点走无头隐身（`StealthyFetcher`，headless），抓不到就跳过，不升级 `real_chrome`。
- **`Candidate` 新增字段必须带默认值放末尾**：现有代码大量用位置参数构造 4 字段 `Candidate`，必须保持向后兼容。
- 注释/文案用中文，与现有代码风格一致。

## 文件结构（本阶段触及）

- **Create** `src/diting/sources/fetch.py` — 抓取内核：`fetch_text(url, *, stealthy, fetcher, timeout_ms) -> str`、`search_engine(query, *, max_results, serp_fetcher) -> list[Candidate]`、`enrich_bodies(...)` 放 `crawl.py`。
- **Create** `tests/test_fetch.py` — 抓取内核单测。
- **Modify** `src/diting/models.py` — `Candidate` 加 `body: str = ""`。
- **Modify** `src/diting/sources/websearch.py` — searxng 空时 fallback。
- **Modify** `src/diting/crawl.py` — 新增 `enrich_bodies`。
- **Modify** `src/diting/novelty.py` / `src/diting/synthesize.py` — 有 body 优先用正文。
- **Modify** `src/diting/config.py` + `config.example.yaml` — 加 `fetch_top_n`、`known_antibot_domains`。
- **Modify** `src/diting/runner.py` — 接线：crawl 后调 `enrich_bodies`。
- **Modify** `pyproject.toml` — dependencies 加 scrapling。

---

### Task 1: 安装 scrapling + 确认抓取 API + 声明依赖

**Files:**
- Modify: `pyproject.toml`（dependencies 列表）

**Interfaces:**
- Produces: 本机 framework python 可 `import scrapling`；确认 `Fetcher().get(url)` / `StealthyFetcher().fetch(url)` 返回对象上取 HTML 的属性名。

- [ ] **Step 1: 安装 scrapling 及其浏览器内核**

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pip install scrapling
# scrapling 需要一次浏览器/依赖初始化（playwright 已装，此步补齐 scrapling 侧）：
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m scrapling install || true
```

- [ ] **Step 2: 确认抓取 API 与取 HTML 的属性**

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 - <<'PY'
from scrapling.fetchers import Fetcher, StealthyFetcher
r = Fetcher().get("https://example.com", timeout=30000)
print("type:", type(r))
print("attrs:", [a for a in dir(r) if not a.startswith("_")])
for attr in ("html_content", "body", "content", "text"):
    v = getattr(r, attr, None)
    print(attr, "->", (v[:60] if isinstance(v, str) else type(v)))
PY
```

Expected: 打印出对象类型与可用属性；至少一个属性是包含 `<html` 的字符串。记下哪个属性给完整 HTML（Task 3 的 `_html_of` 已用多属性兜底，无需改代码，只为确认库可用）。

- [ ] **Step 3: 在 pyproject.toml 声明依赖并提交**

把 `pyproject.toml` 的 dependencies 行改为（在末尾加 scrapling，版本用上一步实际装到的，用 `pip show scrapling` 查 Version）：

```toml
dependencies = ["httpx>=0.27", "pyyaml>=6.0", "trafilatura>=1.12", "lxml_html_clean>=0.1", "scrapling>=0.2"]
```

```bash
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pip show scrapling | grep -i version
cd /Users/<dev-user>/diting-radar
git add pyproject.toml
git commit -m "chore: 引入 scrapling 抓取库依赖"
```

---

### Task 2: Candidate 增加 body 字段

**Files:**
- Modify: `src/diting/models.py:18-23`
- Test: `tests/test_models.py`

**Interfaces:**
- Produces: `Candidate(title, url, summary, source, body="")` — 第 5 个字段 `body: str = ""`，位置构造 4 参数仍合法。

- [ ] **Step 1: 写失败测试**

在 `tests/test_models.py` 末尾追加：

```python
def test_candidate_body_defaults_empty_and_positional_compat():
    from diting.models import Candidate
    c = Candidate("t", "http://u", "摘要", "websearch")   # 旧式 4 位置参数仍合法
    assert c.body == ""
    c2 = Candidate("t", "http://u", "摘要", "websearch", body="正文")
    assert c2.body == "正文"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_models.py::test_candidate_body_defaults_empty_and_positional_compat -v`
Expected: FAIL（`TypeError` 或 `AttributeError: body`）。

- [ ] **Step 3: 加字段**

`src/diting/models.py` 的 Candidate 改为：

```python
@dataclass(frozen=True)
class Candidate:
    title: str
    url: str
    summary: str
    source: str
    body: str = ""
```

- [ ] **Step 4: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿（现有 53 测试不因新字段破坏，新测试 PASS）。

- [ ] **Step 5: 提交**

```bash
git add src/diting/models.py tests/test_models.py
git commit -m "feat: Candidate 增加 body 字段（正文，默认空）"
```

---

### Task 3: 抓取内核 fetch_text（读正文）

**Files:**
- Create: `src/diting/sources/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: `trafilatura.extract`（已装）。
- Produces: `fetch_text(url: str, *, stealthy: bool = False, fetcher=None, timeout_ms: int = 30000) -> str` — 返回正文纯文本；失败/空一律返回 `""`，绝不抛出。`fetcher` 为可注入的 `callable(url, stealthy, timeout_ms) -> html_str`，默认用 scrapling。

- [ ] **Step 1: 写失败测试**

创建 `tests/test_fetch.py`：

```python
from diting.sources.fetch import fetch_text

_HTML = "<html><body><article><p>这是一篇很长很长的核心正文内容。</p></article></body></html>"

def test_fetch_text_extracts_body():
    out = fetch_text("http://x", fetcher=lambda url, stealthy, timeout_ms: _HTML)
    assert "核心正文" in out

def test_fetch_text_returns_empty_on_exception():
    def boom(url, stealthy, timeout_ms): raise RuntimeError("network down")
    assert fetch_text("http://x", fetcher=boom) == ""

def test_fetch_text_returns_empty_on_blank_html():
    assert fetch_text("http://x", fetcher=lambda *a, **k: "") == ""

def test_fetch_text_passes_stealthy_flag():
    seen = {}
    def spy(url, stealthy, timeout_ms): seen["stealthy"] = stealthy; return _HTML
    fetch_text("http://x", stealthy=True, fetcher=spy)
    assert seen["stealthy"] is True
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_fetch.py -v`
Expected: FAIL（`ModuleNotFoundError: diting.sources.fetch`）。

- [ ] **Step 3: 实现 fetch.py**

创建 `src/diting/sources/fetch.py`：

```python
# src/diting/sources/fetch.py
from __future__ import annotations
from typing import Callable
import trafilatura
from diting.models import Candidate


def _html_of(resp) -> str:
    """从 scrapling 返回对象里取出 HTML 字符串（兼容不同版本的属性名）。"""
    for attr in ("html_content", "body", "content", "text"):
        v = getattr(resp, attr, None)
        if isinstance(v, str) and v:
            return v
    return str(resp) if resp else ""


def _scrapling_html(url: str, stealthy: bool, timeout_ms: int) -> str:
    """默认抓取器：普通站点用 Fetcher，反爬站点用无头隐身 StealthyFetcher。"""
    from scrapling.fetchers import Fetcher, StealthyFetcher
    if stealthy:
        return _html_of(StealthyFetcher().fetch(url, headless=True, timeout=timeout_ms))
    return _html_of(Fetcher().get(url, timeout=timeout_ms))


def fetch_text(url: str, *, stealthy: bool = False,
               fetcher: Callable[[str, bool, int], str] | None = None,
               timeout_ms: int = 30000) -> str:
    """抓 url 正文为纯文本。任何失败/空内容一律返回 ""，绝不抛出（precision-first）。"""
    fetcher = fetcher or _scrapling_html
    try:
        html = fetcher(url, stealthy, timeout_ms)
    except Exception:
        return ""
    if not html:
        return ""
    return trafilatura.extract(html) or ""
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_fetch.py -v`
Expected: 4 个测试全 PASS。

- [ ] **Step 5: 提交**

```bash
git add src/diting/sources/fetch.py tests/test_fetch.py
git commit -m "feat: 新增抓取内核 fetch_text（scrapling 抓正文，失败降级返空）"
```

---

### Task 4: 抓取内核 search_engine（DuckDuckGo HTML 兜底搜索）

**Files:**
- Modify: `src/diting/sources/fetch.py`（追加函数）
- Test: `tests/test_fetch.py`（追加）

**Interfaces:**
- Produces: `search_engine(query: str, *, max_results: int = 5, serp_fetcher=None, timeout_ms: int = 30000) -> list[Candidate]` — 抓 DDG HTML 版结果解析为 `source="websearch"` 的 `Candidate`（无 body）；失败返 `[]`。`serp_fetcher` 为可注入 `callable(query, max_results, timeout_ms) -> html_str`。

> 选 DuckDuckGo HTML 版（`https://html.duckduckgo.com/html/`）：免 key、无需 JS、结构稳定。它是 bonus 兜底，失败返 `[]` 不影响 arxiv/hn/github 主力源。

- [ ] **Step 1: 写失败测试**

在 `tests/test_fetch.py` 追加：

```python
from diting.sources.fetch import search_engine

_DDG = (
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Farxiv.org%2Fabs%2F1234&rut=x">Cool Paper</a>'
    '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fgithub.com%2Ffoo%2Fbar">A Repo</a>'
)

def test_search_engine_parses_ddg():
    out = search_engine("rag", serp_fetcher=lambda q, n, t: _DDG)
    urls = [c.url for c in out]
    assert "https://arxiv.org/abs/1234" in urls
    assert out[0].source == "websearch" and out[0].title == "Cool Paper"

def test_search_engine_empty_on_exception():
    def boom(q, n, t): raise RuntimeError("network down")
    assert search_engine("rag", serp_fetcher=boom) == []

def test_search_engine_respects_max_results():
    out = search_engine("rag", max_results=1, serp_fetcher=lambda q, n, t: _DDG)
    assert len(out) == 1
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_fetch.py -k search_engine -v`
Expected: FAIL（`ImportError: cannot import name 'search_engine'`）。

- [ ] **Step 3: 实现 search_engine**

在 `src/diting/sources/fetch.py` 顶部 import 区补充，并追加函数：

```python
import re
from urllib.parse import quote, unquote, urlparse, parse_qs

_DDG_HTML = "https://html.duckduckgo.com/html/"
_RESULT_RE = re.compile(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', re.S)


def _ddg_unwrap(href: str) -> str:
    """DDG html 版链接形如 //duckduckgo.com/l/?uddg=<urlencoded>，解出真实 url。"""
    if "uddg=" in href:
        full = href if href.startswith("http") else "https:" + href
        u = parse_qs(urlparse(full).query).get("uddg", [""])[0]
        return unquote(u)
    return href if href.startswith("http") else ""


def _ddg_html(query: str, max_results: int, timeout_ms: int) -> str:
    from scrapling.fetchers import Fetcher
    return _html_of(Fetcher().get(f"{_DDG_HTML}?q={quote(query)}", timeout=timeout_ms))


def search_engine(query: str, *, max_results: int = 5,
                  serp_fetcher=None, timeout_ms: int = 30000) -> list[Candidate]:
    """抓搜索引擎结果作为 searxng 兜底。失败返 []（precision-first）。"""
    serp_fetcher = serp_fetcher or _ddg_html
    try:
        html = serp_fetcher(query, max_results, timeout_ms)
    except Exception:
        return []
    out: list[Candidate] = []
    for m in _RESULT_RE.finditer(html or ""):
        url = _ddg_unwrap(m.group(1))
        title = re.sub(r"<[^>]+>", "", m.group(2)).strip()
        if url and title:
            out.append(Candidate(title=title, url=url, summary="", source="websearch"))
        if len(out) >= max_results:
            break
    return out
```

- [ ] **Step 4: 跑测试确认通过**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_fetch.py -v`
Expected: 全 PASS（含 Task 3 的 4 个）。

- [ ] **Step 5: 提交**

```bash
git add src/diting/sources/fetch.py tests/test_fetch.py
git commit -m "feat: 抓取内核增加 search_engine（DDG HTML 兜底搜索）"
```

---

### Task 5: websearch 源在 searxng 空时 fallback 到 search_engine

**Files:**
- Modify: `src/diting/sources/websearch.py`
- Test: `tests/test_websearch.py`

**Interfaces:**
- Consumes: `search_engine`（Task 4）。
- Produces: `search_web(query, searxng_url, max_results=5, *, get=httpx.get, search_fn=None) -> list[Candidate]` — searxng 返空/异常时调 `search_fn`（默认 `search_engine`）兜底。

- [ ] **Step 1: 写失败测试**

在 `tests/test_websearch.py` 追加（`_Resp` 已在该文件定义）：

```python
from diting.models import Candidate

def test_search_web_falls_back_when_searxng_empty():
    empty = _Resp({"results": []})
    called = {}
    def fake_search(q, max_results=5):
        called["q"] = q
        return [Candidate("X", "http://x", "", "websearch")]
    out = search_web("rag", "http://sx", get=lambda *a, **k: empty, search_fn=fake_search)
    assert called["q"] == "rag" and out[0].url == "http://x"

def test_search_web_no_fallback_when_searxng_has_results():
    payload = _Resp({"results": [{"title": "T", "url": "http://u", "content": "c"}]})
    def fake_search(q, max_results=5):
        raise AssertionError("有结果就不该兜底")
    out = search_web("q", "http://sx", get=lambda *a, **k: payload, search_fn=fake_search)
    assert out[0].url == "http://u"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_websearch.py -v`
Expected: `test_search_web_falls_back_when_searxng_empty` FAIL（`search_web() got an unexpected keyword argument 'search_fn'`）。

- [ ] **Step 3: 改写 search_web**

把 `src/diting/sources/websearch.py` 的 `search_web` 整体替换为：

```python
def search_web(
    query: str, searxng_url: str, max_results: int = 5, *, get=httpx.get, search_fn=None
) -> list[Candidate]:
    results = []
    try:
        resp = get(
            f"{searxng_url.rstrip('/')}/search",
            params={"q": query, "format": "json"},
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])[:max_results]
    except Exception:
        results = []
    out: list[Candidate] = []
    for r in results:
        title = (r.get("title") or "").strip()
        url = r.get("url") or ""
        if title and url:
            out.append(
                Candidate(
                    title=title,
                    url=url,
                    summary=(r.get("content") or "").strip(),
                    source="websearch",
                )
            )
    if not out:
        from diting.sources.fetch import search_engine
        fn = search_fn or search_engine
        return fn(query, max_results=max_results)
    return out
```

（`extract_main_text` 保持不动，其专测继续通过。）

- [ ] **Step 4: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/sources/websearch.py tests/test_websearch.py
git commit -m "feat: websearch 在 searxng 空时 fallback 到 search_engine"
```

---

### Task 6: config 增加 fetch_top_n 与 known_antibot_domains

**Files:**
- Modify: `src/diting/config.py`
- Modify: `config.example.yaml`
- Test: `tests/test_config.py`

**Interfaces:**
- Produces: `Config.fetch_top_n: int`（默认 5）、`Config.known_antibot_domains: tuple[str, ...]`（默认 `("zhihu.com", "csdn.net")`）；从 `raw["crawl"]` 读、缺省用默认。

- [ ] **Step 1: 写失败测试**

在 `tests/test_config.py` 追加：

```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -v`
Expected: 新两测 FAIL（`AttributeError: 'Config' object has no attribute 'fetch_top_n'`）。

- [ ] **Step 3: 加字段**

`src/diting/config.py` 的 `Config` 末尾加两字段（带默认，放在 `state_dir` 之后）：

```python
    state_dir: str
    fetch_top_n: int = 5
    known_antibot_domains: tuple[str, ...] = ("zhihu.com", "csdn.net")
```

`load_config` 的 `Config(...)` 构造里，在 `state_dir=...` 之后补两行：

```python
            state_dir=raw["state_dir"],
            fetch_top_n=int(raw["crawl"].get("fetch_top_n", 5)),
            known_antibot_domains=tuple(raw["crawl"].get("known_antibot_domains", ["zhihu.com", "csdn.net"])),
```

- [ ] **Step 4: 更新 config.example.yaml**

把 `config.example.yaml` 的 `crawl:` 段改为：

```yaml
crawl:
  searxng_url: "http://localhost:8080"      # ✅ 已核对：本机 searxng 实例
  github_token_env: "GITHUB_TOKEN"
  fetch_top_n: 5                            # 每轮对去重后前 N 条候选抓正文喂大模型
  known_antibot_domains: ["zhihu.com", "csdn.net"]  # 这些域走无头隐身抓，抓不到就跳过
```

- [ ] **Step 5: 跑测试 + 提交**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_config.py -v`
Expected: 全 PASS。

```bash
git add src/diting/config.py config.example.yaml tests/test_config.py
git commit -m "feat: config 增加 fetch_top_n 与 known_antibot_domains"
```

---

### Task 7: enrich_bodies 正文注入 + 接线 run_report

**Files:**
- Modify: `src/diting/crawl.py`（新增 `enrich_bodies`）
- Modify: `src/diting/runner.py`（`run_report` / `_collect_candidates` 接线）
- Test: `tests/test_crawl.py`、`tests/test_runner.py`（现有 research 调用补 no-op enrich）

**Interfaces:**
- Consumes: `fetch_text`（Task 3）、`Config.fetch_top_n`/`known_antibot_domains`（Task 6）。
- Produces: `enrich_bodies(candidates: list[Candidate], top_n: int, antibot_domains: tuple[str, ...] = (), *, fetch=fetch_text) -> list[Candidate]` — 对前 `top_n` 条候选抓正文，命中反爬域走 `stealthy=True`，抓到的用 `dataclasses.replace` 写入 `body`；其余原样返回。`run_report(..., enrich=enrich_bodies)` 新增可注入参数。

- [ ] **Step 1: 写 enrich_bodies 失败测试**

在 `tests/test_crawl.py` 追加：

```python
from diting.crawl import enrich_bodies

def test_enrich_bodies_fetches_top_n_only():
    cands = [Candidate(f"t{i}", f"http://u{i}", "", "websearch") for i in range(4)]
    calls = []
    def fake_fetch(url, *, stealthy=False): calls.append(url); return "正文-" + url
    out = enrich_bodies(cands, top_n=2, fetch=fake_fetch)
    assert calls == ["http://u0", "http://u1"]
    assert out[0].body == "正文-http://u0"
    assert out[2].body == ""           # top_n 之外不抓

def test_enrich_bodies_uses_stealthy_for_antibot_domain():
    cands = [Candidate("t", "https://zhuanlan.zhihu.com/p/1", "", "websearch")]
    seen = {}
    def fake_fetch(url, *, stealthy=False): seen["stealthy"] = stealthy; return "正文"
    enrich_bodies(cands, top_n=1, antibot_domains=("zhihu.com",), fetch=fake_fetch)
    assert seen["stealthy"] is True

def test_enrich_bodies_keeps_original_when_fetch_empty():
    cands = [Candidate("t", "http://u", "原摘要", "websearch")]
    out = enrich_bodies(cands, top_n=1, fetch=lambda url, *, stealthy=False: "")
    assert out[0].body == "" and out[0].summary == "原摘要"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_crawl.py -k enrich -v`
Expected: FAIL（`ImportError: cannot import name 'enrich_bodies'`）。

- [ ] **Step 3: 实现 enrich_bodies**

`src/diting/crawl.py` 顶部 import 区改为：

```python
from __future__ import annotations
import dataclasses
from typing import Callable
from diting.models import Candidate
from diting.sources.fetch import fetch_text
```

在文件末尾追加：

```python
def enrich_bodies(candidates: list[Candidate], top_n: int,
                  antibot_domains: tuple[str, ...] = (), *, fetch=fetch_text) -> list[Candidate]:
    """对前 top_n 条候选抓正文填入 body；命中反爬域走无头隐身；抓不到保持原样。"""
    out: list[Candidate] = []
    for i, c in enumerate(candidates):
        if i < top_n:
            stealthy = any(d in c.url for d in antibot_domains)
            body = fetch(c.url, stealthy=stealthy)
            out.append(dataclasses.replace(c, body=body) if body else c)
        else:
            out.append(c)
    return out
```

- [ ] **Step 4: 跑 enrich 测试确认通过**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_crawl.py -v`
Expected: 全 PASS。

- [ ] **Step 5: 接线 run_report + 适配 test_runner**

`src/diting/runner.py`：import 区加 `from diting.crawl import run_crawl, enrich_bodies`（替换原 `from diting.crawl import run_crawl`）。

`_collect_candidates` 签名加 `enrich` 参数，研究/loops 分支接线：

```python
def _collect_candidates(lens: str, cfg, client, store, interests: Interests,
                        profile: dict, sources, enrich=enrich_bodies) -> tuple[list, list[str], dict]:
```

把该函数 research/loops 分支结尾改为：

```python
    # research / loops — original path
    queries = generate_queries(client, lens, interests, profile)
    candidates, notes = run_crawl(queries, sources or build_sources(cfg))
    candidates = enrich(candidates, cfg.fetch_top_n, cfg.known_antibot_domains)
    return candidates, notes, {}
```

`run_report` 签名加 `enrich=enrich_bodies`，并把它传进 `_collect_candidates`：

```python
def run_report(lens, cfg, client, store, *, now_ts=None, sources=None,
               feishu_run=subprocess.run, enrich=enrich_bodies) -> Report:
```

```python
        candidates, notes, pending = _collect_candidates(
            lens, cfg, client, store, interests, profile,
            sources or build_sources(cfg), enrich=enrich,
        )
```

在 `tests/test_runner.py` 把 research 镜头那 3 处 `run_report("research", ...)` 调用各加一个 no-op enrich（避免单测联网），即在每个调用的关键字参数里追加 `enrich=lambda c, *a, **k: c`。例如 `test_run_report_end_to_end` 的两处：

```python
    report = run_report("research", cfg, RouterClient(), store,
                        now_ts=_NOW, sources=fake_sources, feishu_run=fake_feishu,
                        enrich=lambda c, *a, **k: c)
```

（`test_run_report_degrades_when_llm_fails`、`test_run_report_empty_skips_feishu` 同样加 `enrich=lambda c, *a, **k: c`；trends 测试不走 enrich，不用改。）

- [ ] **Step 6: 全套回归 + 提交**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿（含新增，且无联网）。

```bash
git add src/diting/crawl.py src/diting/runner.py tests/test_crawl.py tests/test_runner.py
git commit -m "feat: 正文注入 enrich_bodies 并接入 run_report（top-N 抓正文）"
```

---

### Task 8: 下游 novelty / synthesize 优先用正文

**Files:**
- Modify: `src/diting/novelty.py:17`
- Modify: `src/diting/synthesize.py:35`
- Test: `tests/test_novelty.py`、`tests/test_synthesize.py`

**Interfaces:**
- Consumes: `Candidate.body`。
- Produces: 行为变更——有 `body` 时喂大模型用正文（截断），否则用 `summary`；外部签名不变。

- [ ] **Step 1: 写失败测试**

在 `tests/test_novelty.py` 追加：

```python
from diting.models import Candidate
from diting.novelty import judge_novelty

def test_judge_novelty_uses_body_when_present():
    captured = {}
    class C:
        def complete_json(self, messages, **kw):
            captured["user"] = messages[1]["content"]
            return {"novel_urls": ["http://a"]}
    cands = [Candidate("t", "http://a", "短摘要", "arxiv", body="完整正文关键词ZYX")]
    judge_novelty(C(), cands, "ctx")
    assert "完整正文关键词ZYX" in captured["user"]
```

在 `tests/test_synthesize.py` 追加：

```python
from diting.models import Candidate, Interests
from diting.synthesize import synthesize

def test_synthesize_feeds_body_when_present():
    captured = {}
    class C:
        def complete_json(self, messages, **kw):
            captured["user"] = messages[1]["content"]
            return {"items": []}
    cands = [Candidate("t", "http://a", "短摘要", "arxiv", body="正文独有词WQX")]
    synthesize(C(), "research", "2026-06-18", cands, Interests((), (), (), ()))
    assert "正文独有词WQX" in captured["user"]
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_novelty.py tests/test_synthesize.py -k body -v`
Expected: 两测 FAIL（喂的是 summary，不含 body 关键词）。

- [ ] **Step 3: 改 novelty 与 synthesize**

`src/diting/novelty.py` 的 listing 行（第 17 行）改为优先用 body：

```python
    listing = "\n".join(f"- {c.url} | {c.title} | {(c.body or c.summary)[:600]}" for c in candidates)
```

`src/diting/synthesize.py` 的候选上下文（第 35 行 `"summary": c.summary[:300]`）改为：

```python
               "candidates": [{"url": c.url, "title": c.title,
                               "summary": (c.body or c.summary)[:600],
                               "source": c.source} for c in candidates]}
```

- [ ] **Step 4: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/novelty.py src/diting/synthesize.py tests/test_novelty.py tests/test_synthesize.py
git commit -m "feat: novelty/synthesize 有正文时优先用正文判断"
```

---

### Task 9: 修 `来源:?`（synthesize 的 URL 规范化匹配）

**Files:**
- Modify: `src/diting/synthesize.py:41,45`
- Test: `tests/test_synthesize.py`

**Interfaces:**
- Produces: 行为变更——LLM 回的 url 与候选 url 仅差末尾 `/` 时，仍能匹配到正确 `source`，不再回退 `"?"`。签名不变。

- [ ] **Step 1: 写失败测试**

在 `tests/test_synthesize.py` 追加：

```python
def test_synthesize_matches_source_despite_trailing_slash():
    class C:
        def complete_json(self, messages, **kw):
            return {"items": [{"url": "http://a/", "title": "t",
                               "one_liner": "x", "why_it_matters": "y"}]}
    cands = [Candidate("t", "http://a", "s", "arxiv")]   # 候选无斜杠，LLM 回带斜杠
    rep = synthesize(C(), "research", "2026-06-18", cands, Interests((), (), (), ()))
    assert rep.items[0].source == "arxiv"   # 不再回退 "?"
```

- [ ] **Step 2: 跑测试确认失败**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest tests/test_synthesize.py -k trailing_slash -v`
Expected: FAIL（`assert '?' == 'arxiv'`）。

- [ ] **Step 3: 规范化匹配**

`src/diting/synthesize.py` 在 `synthesize` 函数内，把 `by_url` 构造与 source 取值改为规范化（去末尾斜杠）匹配。即把第 41 行与第 45 行所在的 items 构造块改为：

```python
        def _norm(u: str) -> str:
            return (u or "").rstrip("/")
        by_url = {_norm(c.url): c for c in candidates}
        items = tuple(
            RankedItem(title=it.get("title", ""), url=it.get("url", ""),
                       one_liner=it.get("one_liner", ""), why_it_matters=it.get("why_it_matters", ""),
                       source=by_url.get(_norm(it.get("url", "")), Candidate("", "", "", "?")).source, lens=lens)
            for it in data.get("items", []) if it.get("url")
        )
```

- [ ] **Step 4: 跑测试确认通过 + 全套回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿。

- [ ] **Step 5: 提交**

```bash
git add src/diting/synthesize.py tests/test_synthesize.py
git commit -m "fix: synthesize 用规范化 URL 匹配来源，修 来源:? 回退"
```

---

### Task 10: 整合回归 + 真跑验收（部署）

**Files:** 无（验证 + 部署）

**Interfaces:** 无新增。

- [ ] **Step 1: 全套测试回归**

Run: `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q`
Expected: 全绿（原 53 + 本阶段新增约 13 个）。**必须由控制器亲自核实真实数字**（历史教训：别全信子代理报告）。

- [ ] **Step 2: 真跑一轮 research 验收（需 DeepSeek key）**

```bash
cd /Users/<dev-user>/diting-radar
bash scripts/run-lens.sh research
tail -30 state/cron-research.log
```
Expected: 日志显示爬到候选并抓了正文；产出的情报里来源标签不再清一色 `?`；飞书/Obsidian 收到。若 searxng 仍空，应看到 DDG 兜底产出 websearch 候选。

- [ ] **Step 3: 确认 launchd 定时仍在（本阶段未改定时，只验证未被破坏）**

```bash
launchctl list | grep diting
```
Expected: research/loops/trends 三任务都在。

- [ ] **Step 4: 提交收尾（若 Step 2 真跑产生了 state 外的可提交变更，通常无）**

本阶段代码已在前序任务逐个提交，此处一般无新增。如有遗漏：

```bash
cd /Users/<dev-user>/diting-radar && git status
```

---

## Self-Review

**1. Spec 覆盖（阶段一部分）**
- 抓取内核 `fetch_text`（读正文 / 反爬走无头隐身 / 失败降级返空）→ Task 3 ✅
- 抓取内核 `search_engine`（searxng 兜底搜索）→ Task 4 ✅
- websearch 在 searxng 空时 fallback → Task 5 ✅
- 候选 top-N 抓正文注入 `Candidate.body` → Task 2（字段）+ Task 7（注入）✅
- 下游 novelty/synthesize 有正文时优先用正文 → Task 8 ✅
- 修 `来源:?` → Task 9 ✅
- config 新增 `fetch_top_n`/`known_antibot_domains` → Task 6 ✅
- 依赖声明 scrapling → Task 1 ✅
- 单测隔离不联网（注入 fetcher/enrich）→ Task 3/4/5/7 的注入点 ✅
- （阶段二 dig 镜头不在本计划，另起）

**2. 占位符扫描**：无 TBD/TODO/"add error handling"/"similar to"；每个代码步骤都有完整可粘贴代码。Task 1 为 setup（装库），无 TDD 是合理的。

**3. 类型/签名一致性**：
- `fetch_text(url, *, stealthy, fetcher, timeout_ms)`（Task 3）↔ `enrich_bodies` 内 `fetch(c.url, stealthy=stealthy)` 与测试 `fake_fetch(url, *, stealthy=False)`（Task 7）一致。
- `search_engine(query, *, max_results, serp_fetcher, timeout_ms)`（Task 4）↔ websearch fallback `fn(query, max_results=max_results)`（Task 5）一致。
- `Candidate(..., body="")`（Task 2）被 Task 7/8/9 一致引用。
- `run_report(..., enrich=enrich_bodies)`（Task 7）↔ test_runner 注入 `enrich=lambda c, *a, **k: c` 一致。
- `Config.fetch_top_n`/`known_antibot_domains`（Task 6）↔ runner `cfg.fetch_top_n`/`cfg.known_antibot_domains`（Task 7）一致。

无遗留问题。
