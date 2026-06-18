# 谛听 v2 实现计划 — 另两镜头 + 三时段定时

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development（或 executing-plans）逐任务执行。Steps 用 `- [ ]`。
> **前置**：v1 已合并 main（引擎 + 🔭科研雷达端到端，37 测试绿）。v2 在此之上加 🧩悬而未决+反方、🛰️趋势保鲜、launchd 定时。共用 v1 的整条引擎（signal→query→crawl→novelty→synthesize→deliver），多数是"换 prompt 角度 + 一个新源 + 定时配置"。

**Goal:** 把三镜头补齐（v1 已有 research），加 GitHub release 版本哨兵，并用 launchd 让三份报告每天 10:00/14:00/18:00 自动跑。

**Architecture:** 复用 v1 流水线。loops/trends 镜头主要是 `query.py` 的镜头 prompt + `synthesize` 的角度；trends 额外需要一个"GitHub releases 源"和 `versions.json` 版本快照做 diff（只报出了新版的）。定时用 launchd LaunchAgent，每个 plist 跑一个镜头。

## Global Constraints
（同 v1）Python 3.11+；全程 DeepSeek V4 Pro；不可变数据；小文件；错误显式、源降级 []；precision-first 空则诚实、空报告不刷飞书（v1 已实现）；跑 Mac Studio 不碰 8088；测试 mock 外部 I/O；环境用 `python -m pip` / `python -m pytest`（python alias→framework 坑）。

## 环境/部署注记（来自 v1 验收）
- arXiv 必须 https（v1 已修）；查询要短关键词（v1 已修）。
- searxng 上游引擎可能要代理 → v1 验收时 websearch 空；trends/loops 不依赖 searxng 也能工作。
- 真跑前：`config.yaml` 填 `feishu_target`（飞书 open_id）+ `export DEEPSEEK_API_KEY=`（macstudio openclaw deepseek key）。

---

## Task 1: loops 镜头（悬而未决 + 反方/唱反调）

**Files:** Modify `src/diting/query.py`（加 lens prompt）；Modify `src/diting/synthesize.py`（按 lens 选系统 prompt）；Test `tests/test_query.py`、`tests/test_synthesize.py`（加 loops 用例）

**做什么：** loops 镜头读 `interests.open_loops` + `interests.decisions`，生成两路查询——正向"别人怎么解你卡的问题"、反向"你今天决策的缺点/反例/为什么不该用"。合成时给反方更显眼的呈现。

- [ ] **Step 1: 加 loops 的镜头 prompt（`query.py` 的 `_LENS_PROMPT`）**
```python
    "loops": "镜头=悬而未决+反方。针对用户的 open_loops(卡点/TODO) 和 decisions(今日决策)，"
             "生成两类英文短关键词查询：(a) 解决卡点的 how-to/best-practice；"
             "(b) 唱反调——对每个 decision 找 'X drawbacks / X vs / why not X / X failure'。",
```
- [ ] **Step 2: `generate_queries` 已把 open_loops 传进 ctx；补传 decisions**
  在 `query.py` 的 `ctx` 里加 `"decisions": list(interests.decisions)`，让反方查询能用到决策。
- [ ] **Step 3: 合成按 lens 选系统 prompt（`synthesize.py`）**
  把 `_SYSTEM` 拆成 dict：research 保持现状；loops 版强调"区分'解法'和'反对证据'两类，反方证据要点明它质疑你的哪个决策"。`synthesize(...)` 按 `lens` 取对应 system。
- [ ] **Step 4: 测试** — `test_query.py` 加 `test_generate_loops_queries`（断言反方关键词如 "drawbacks"/"vs" 思路进 prompt）；`test_synthesize.py` 加 loops 用例。`python -m pytest -q` 全绿。
- [ ] **Step 5: 提交** `feat: loops 镜头（悬而未决+反方）`

---

## Task 2: GitHub releases 源 + 版本快照 diff

**Files:** Create `src/diting/sources/github_releases.py`；Modify `src/diting/state.py`（versions.json）；Test `tests/test_github_releases.py`、`tests/test_state_versions.py`

**做什么：** 给一个 repo（`owner/name`），查最新 release/tag；和 `versions.json` 里上次见到的版本比，**只有出了新版才返回 Candidate**（标题含新旧版本号），否则 []。

- [ ] **Step 1: `state.py` 加版本快照存取**
```python
    def get_seen_version(self, repo: str) -> str | None: ...   # 读 versions.json
    def set_seen_version(self, repo: str, version: str) -> None: ...  # 写
```
（versions.json 路径 `state_dir/versions.json`，结构 `{repo: version}`，与 pushed.db 同级）
- [ ] **Step 2: 写失败测试 `test_state_versions.py`**（首次 None；set 后能读回）→ 实现 → 绿。
- [ ] **Step 3: `github_releases.py`**
```python
def check_repo_release(repo: str, store, *, get=httpx.get, token=None) -> list[Candidate]:
    # GET https://api.github.com/repos/{repo}/releases/latest -> tag_name
    # 出错或无 release -> []
    # tag == store.get_seen_version(repo) -> []（没新版）
    # 否则 store.set_seen_version(repo, tag) 并返回 1 个 Candidate(
    #   title=f"{repo} 出新版 {tag}", url=release html_url, summary=release name/body[:300], source="github_release")
```
- [ ] **Step 4: 测试 `test_github_releases.py`**（mock get：首次见→返回1条且写快照；同版本再查→[]；新版→返回）。
- [ ] **Step 5: 提交** `feat: GitHub release 版本哨兵 + versions.json diff`

---

## Task 3: trends 镜头接入流水线（关注清单 → repo → 版本哨兵）

**Files:** Modify `src/diting/runner.py`；Modify `src/diting/signal/profile.py`（清单含 repo 列表）；Test `tests/test_runner.py`

**做什么：** trends 镜头不走"生成自由查询→爬"，而是把关注清单里的 **GitHub repo 列表**（如 `ml-explore/mlx`、`ggml-org/llama.cpp`、`qdrant/qdrant`…）逐个过 Task 2 的版本哨兵，凑成候选，再走 novelty/synthesize/deliver。

- [ ] **Step 1: 关注清单加 `repos` 字段**
  `profile.py` 的 `seed_profile`/默认结构加 `"repos": []`；seed prompt 额外抽"用户依赖的 GitHub 项目，给 owner/name 形式"。`state.py` 的 `_DEFAULT_PROFILE` 加 `"repos": []`。
- [ ] **Step 2: `run_report` 按 lens 分流**
  在 `runner.py` 里，当 `lens == "trends"`：跳过 `generate_queries`/`run_crawl`，改为
```python
        candidates = []
        notes = []
        for repo in profile.get("repos", []):
            candidates += check_repo_release(repo, store, token=os.environ.get(cfg.github_token_env))
        if not candidates:
            notes = ["所有关注 repo 都没出新版"]
```
  其余（filter_unpushed / judge_novelty / synthesize / deliver）不变。research/loops 仍走原 crawl 路径。建议把"取候选"抽成 `_collect_candidates(lens, ...)` 一个函数，保持 run_report 干净。
- [ ] **Step 3: 测试**（`test_runner.py` 加 `test_trends_uses_release_watcher`：profile.repos=["a/b"]，mock check_repo_release 返回1条→报告非空且走完投递；版本无变化→空报告不刷飞书）。`python -m pytest -q` 全绿。
- [ ] **Step 4: 提交** `feat: trends 镜头接入（关注 repo 版本哨兵）`

---

## Task 4: launchd 三时段定时

**Files:** Create `scripts/launchd/ai.diting.research.plist`、`...loops.plist`、`...trends.plist`、`scripts/install-launchd.sh`、`scripts/run-lens.sh`

**做什么：** 每天 10:00 research / 14:00 loops / 18:00 trends 各跑一次。launchd 的 `StartCalendarInterval` 触发；每个 job 跑 `run-lens.sh <lens>`，脚本负责 `export DEEPSEEK_API_KEY`（从 macstudio openclaw 取或本地 keychain）+ 用 framework python 跑 `python -m diting run --lens <lens>`。

- [ ] **Step 1: `scripts/run-lens.sh`**
```bash
#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/diting-radar"
PYBIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3
# DeepSeek key：从 macstudio openclaw 取（也可改成本地 keychain）
export DEEPSEEK_API_KEY="$(ssh -o ConnectTimeout=20 macstudio 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(chr(126)+\"/.openclaw/openclaw.json\")))[\"models\"][\"providers\"][\"deepseek\"][\"apiKey\"])"')"
export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
exec "$PYBIN" -m diting run --lens "$1" >> "$HOME/diting-radar/state/cron-$1.log" 2>&1
```
- [ ] **Step 2: 三个 plist**（示例 research，10:00）
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>ai.diting.research</string>
  <key>ProgramArguments</key><array>
    <string>/bin/bash</string><string>/Users/<dev-user>/diting-radar/scripts/run-lens.sh</string><string>research</string>
  </array>
  <key>StartCalendarInterval</key><dict><key>Hour</key><integer>10</integer><key>Minute</key><integer>0</integer></dict>
  <key>StandardErrorPath</key><string>/Users/<dev-user>/diting-radar/state/launchd-research.err</string>
</dict></plist>
```
  loops 用 14:00、trends 用 18:00，Label 对应改。
- [ ] **Step 3: `scripts/install-launchd.sh`** —— `cp scripts/launchd/*.plist ~/Library/LaunchAgents/` 然后 `launchctl load -w ~/Library/LaunchAgents/ai.diting.*.plist`（含 unload 旧的、打印 `launchctl list | grep diting`）。
- [ ] **Step 4: 手动验收** —— 跑 `launchctl start ai.diting.research` 立即触发一次，看 `state/cron-research.log` 和真实 Obsidian Inbox + 飞书。确认三镜头三时段都注册。
- [ ] **Step 5: 提交** `feat: launchd 三时段定时（10/14/18 三镜头）`

---

## Self-Review（对照 design §5/§12/§18）
- 三镜头齐：research(v1) + loops(T1) + trends(T2/T3) ✅
- 版本哨兵 + versions.json：design §13 的 versions.json 落在 T2 ✅
- 三时段双通道：T4 launchd ✅；双通道复用 v1 deliver ✅
- 全程 DeepSeek V4 Pro、不碰 8088、空报告不刷飞书：复用 v1 ✅
- 反馈闭环（点有用/没用自学习）仍留 v3（design §15 v2 项里最重的，单独再开一计划）。

## 不在 v2 范围（留 v3）
- 反馈闭环自学习；中文生态源（知乎/公众号）；searxng 走代理修复；二奢生意情报镜头。

