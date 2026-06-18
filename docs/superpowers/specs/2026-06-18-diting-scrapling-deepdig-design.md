# 谛听 · 网搜深化 + 自动深挖镜头 设计

> 创建：2026-06-18 ｜ 状态：已批准，待写实现计划
> 前置设计：`2026-06-18-diting-radar-design.md`（v1+v2 引擎）
> 一句话：给谛听补一个共用的 scrapling 抓取内核，先把日常三镜头的网搜修强（搜得到 + 读正文），再加一个每天一次的自动深挖镜头。

## 1. 背景与动机

当前网搜环节有两个真问题：

1. **不读正文**：`sources/websearch.py` 的 `search_web` 只取 searxng 返回的标题 + 一句话摘要，`extract_main_text()` 定义了却从未被调用——候选从来没有被读过正文。"砍已知"和"为什么对你重要"的合成因此缺真材料。
2. **搜索常空**：searxng 上游引擎需要代理，经常返回空 `results`，websearch 源整轮空转（STATUS 已记录的 `来源:?` 和"websearch 没取到"即此）。

scrapling 是个 Python 抓取库（隐身抓取、可抗反爬、自带正文抽取），本机的 MCP 封装只是外壳。谛听是无人值守的 Python 进程，调不到 MCP，但可以 `import scrapling` 直接当库用。

## 2. 目标 / 非目标

**目标**
- A. 日常三镜头（research/loops）的网搜：搜得到（scrapling 兜底 searxng）+ 真读正文喂大模型。
- B. 新增 `dig`（深挖）镜头：每天自动挖 1 个话题，产出 Obsidian 长资料 + 飞书短通知。
- A、B 共用同一个抓取内核。

**非目标（YAGNI 边界）**
- 不推倒重构现有 arxiv/hackernews/github/github_releases 四个源（它们工作正常）。
- 不照搬 deep-knowledge-crawl 的"派子 agent 提炼"（无人值守环境没有 Agent 工具）——提炼一律走 DeepSeek。
- 不硬刚反爬：自动模式不调起真 Chrome（无人值守/锁屏起不可靠）；抓不到就跳过。
- 不引入 GPT-Researcher（重，暂不需要）。

## 3. 总体架构

```
                 ┌─────────────────────────────┐
                 │  抓取内核 sources/fetch.py   │  ← 新增，封装 scrapling
                 │  fetch_text(url) -> str      │     普通快抓 / 反爬无头隐身 / 抓不到返回 ""
                 │  search_engine(q) -> [Cand]  │     scrapling 抓搜索引擎结果
                 └──────────┬──────────────────┘
          ┌─────────────────┴──────────────────┐
          ▼                                     ▼
  阶段一：日常网搜增强                    阶段二：dig 深挖镜头（新）
  - websearch 源：searxng 优先，          - 选题：dig_queue.yaml 优先，空了从兴趣自动选
    空了 fallback 到 search_engine        - 多角度搜 → 深抓正文 → (可选) gh 扒代码仓
  - 候选 top-N 抓正文注入 Candidate.body  - 喂 DeepSeek 综合成长资料
  - 喂 judge_novelty / synthesize         - 产出 Obsidian reference-manual + 飞书短通知
```

## 4. 模块设计

### 4.1 抓取内核 `src/diting/sources/fetch.py`（新增）

纯函数式，依赖注入便于测试（mock scrapling）。

```python
def fetch_text(url: str, *, stealthy: bool = False,
               fetcher=None, timeout_ms: int = 30000) -> str:
    """抓 url 正文为纯文本/markdown。
    普通站点用 Fetcher.get；stealthy=True 用 StealthyFetcher（无头隐身，headless）。
    任何异常 / 抓不到 → 返回 ""（调用方据空串跳过）。绝不抛出。"""

def search_engine(query: str, *, max_results: int = 5, fetcher=None) -> list[Candidate]:
    """用 scrapling 抓搜索引擎结果，产出 source='websearch' 的 Candidate（无正文）。
    失败返回 []。"""
```

- 反爬策略：默认 `stealthy=False`（快抓）；调用方对已知反爬域名（知乎/csdn 等）传 `stealthy=True`，仍是无头（`headless=True`、`real_chrome=False`）。抓不到一律空串跳过，不升级真 Chrome。
- scrapling 真实 API 名以安装后为准（`Fetcher` / `StealthyFetcher` 或 `DynamicFetcher`），实现时核对；接口签名对外稳定。

### 4.2 阶段一 · 日常网搜增强

- **`sources/websearch.py` 改造**：`search_web` 保持 searxng 优先；当 searxng 返回空时 fallback 调 `search_engine(query)`。signature 兼容现状（注入 `get` 不变）。
- **正文注入**：在 `crawl.py` 的 `run_crawl` 之后（或 `runner._collect_candidates` 内 research/loops 分支），对去重后的候选取 **top-5** 调 `fetch_text` 填入 `Candidate.body`。已知反爬域走 `stealthy=True`。
- **下游用正文**：`novelty.judge_novelty` 与 `synthesize.synthesize` 的 prompt 在有 `body` 时优先用正文（截断到约 2-3k 字符）判断新颖度与"为何重要"，并据此修 `来源:?`（有正文则 URL/来源可靠匹配）。
- **数据模型**：`models.Candidate` 增加字段 `body: str = ""`（frozen dataclass，默认空，向后兼容）。

### 4.3 阶段二 · `dig` 深挖镜头

- **选题** `signal/dig_topics.py`（新增）：
  - 读 `state/dig_queue.yaml`（用户手写的"想挖清单"，gitignore）；非空 → 取第一个未挖过的话题。
  - 清单空 → 从 `interests.topics` + profile 选一个"挖过登记表"里没有的高频话题。
  - 都没有新题 → 返回 None（当天 dig 跳过，不硬凑，空报告不刷飞书）。
- **去重登记**：`StateStore` 增加 `is_dug(topic)` / `mark_dug(topic)`（存 `state/dug_topics.json` 或 pushed.db 新表）；投递成功后才登记（与 trends 快照同款"投递后推进"原则）。
- **流程** `dig.py`（新增，或 runner 内 dig 分支）：
  1. 一个话题 → 生成 4-6 个多角度查询（复用/扩展 `query.generate_queries`，dig 专用 prompt）。
  2. 每个查询 → `search_engine` 搜 → 合并去重 → 取 top-N（封顶 **10-15** 篇）`fetch_text` 深抓正文。
  3. （可选）`gh` 扒最相关代码仓（subprocess，复用现有 github token）。
  4. 抓回的正文逐篇/分批喂 DeepSeek（`complete`/`complete_json`），综合成结构化中文长资料。
- **防失控**：每轮只挖 1 题；来源数封顶；单篇正文截断后喂模型；整轮总超时；异常降级（同 v1 的 DeepSeek 故障降级告警）。
- **产出**：
  - Obsidian：`谛听深挖/YYYY-MM-DD <话题>.md`，`type: reference-manual`，5 字段 frontmatter，日期前缀。结构：论文/代码仓清单（带链接 + 一句话价值）+ 分主题核心知识 + 对本项目的直接建议 + 跨来源共识/分歧。
  - 飞书：短通知（话题 + 一句话价值 + Obsidian 文档位置），走现有 `--as bot`。

## 5. 配置与状态变更

- `config.yaml` / `config.example.yaml` 新增：`dig_vault_dir`（默认 `…/claude/谛听深挖`）、`known_antibot_domains`（默认含 zhihu.com / csdn.net）、`fetch_top_n`（默认 5）、`dig_max_sources`（默认 12）。
- `state/`（gitignore）新增：`dig_queue.yaml`（用户手写清单）、`dug_topics.json`（已挖登记）。

## 6. 错误处理与降级

- 抓取内核任何失败 → 返回空，不抛出，调用方跳过该来源（precision-first：宁缺毋滥）。
- 反爬站抓不到 → 跳过，不升级真 Chrome。
- DeepSeek 不可用 → 沿用 v1 降级告警路径。
- dig 无新题 / 全部来源抓空 → 空报告，不刷飞书、不登记。

## 7. 测试计划（沿用 TDD，在现有 53 测试上增量）

- 抓取内核：mock fetcher，测普通抓取、反爬走 stealthy、抓不到返回空、`search_engine` 解析与失败返 []。
- 日常增强：searxng 空时 fallback 到 search_engine；top-N 正文注入；有 body 时下游 prompt 用正文；`来源:?` 修复。
- dig 镜头：选题（清单优先 / 自动选 / 去重 / 无题返回 None）；综合产出非空；投递成功才 `mark_dug`；空话题不跑不刷飞书。

## 8. 部署与依赖

- `pip install scrapling`（装到谛听用的 framework python，与 httpx/trafilatura 同环境）；playwright 已在，按需 `playwright install chromium` 拉浏览器内核。
- 更新 requirements、`scripts/deploy.sh`。
- 新增 launchd plist `ai.diting.dig`，每天 **20:00** 跑 `run-lens.sh dig`。

## 9. 分阶段交付顺序

1. **抓取内核 + 阶段一**（小、风险低、马上见效）：fetch.py + websearch fallback + 正文注入 + 下游用正文 + 测试。验证日常情报变准。
2. **阶段二 dig 镜头**：选题 + dig 流程 + 产出 + 去重登记 + launchd 20:00 + 测试。
3. 部署：装库 + 重装 launchd + 真跑验收一轮 dig。
