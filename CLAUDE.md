# 谛听 · 个人技术情报雷达 — Claude 操作手册

> **如果用户明确让你"继续项目"或贴了 ONBOARDING 口令，优先读 `ONBOARDING.md`。**
>
> 新 Claude 进门先读这份，30 秒掌握地形。详细进度见 `STATUS.md`，完整设计见 `docs/superpowers/specs/2026-06-18-diting-radar-design.md`。

## 一句话

谛听：每天读你做过的事 → DeepSeek V4 Pro 蒸出兴趣 → 爬全网 → 砍已知 → 合成"为何重要"的技术情报 → 飞书 + Obsidian 双通道。Python 3.11，**运行在 Mac Studio（<run-user>）launchd**（2026-06-18 从 MacBook 迁来），服务用户本人。

## 🔴 地理：源码在哪，运行在哪（2026-06-18 迁移后）

| 位置 | 角色 | 路径 |
|------|------|------|
| **MacBook（开发机）** | 源码主分支 + 开发/测试/commit | `/Users/<dev-user>/diting-radar`（framework python） |
| **Mac Studio（运行机 <run-user>，24h）** | **实际跑 launchd 的地方** | `/Users/<run-user>/diting-radar`（venv `.venv/bin/python`）+ `~/Library/LaunchAgents/ai.diting.*.plist` |
| **GitHub** | 远程备份 | `https://github.com/hailanlan0577/diting-radar`（public） |

> 开发在 MacBook，运行在 Mac Studio（SSH 别名 `macstudio`）。改代码流程见下方「部署工作流」。

**禁忌：**
- ❌ **MacBook 上**不要用裸 `python`（alias 到 framework）—— 用全路径 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3`；**Mac Studio 上**用 venv `~/diting-radar/.venv/bin/python`
- ❌ 飞书发消息不要漏 `--as bot`（否则进看不到的自聊）
- ❌ 不要把 `config.yaml` / `~/.diting.env` 推 git
- ❌ **scrapling 要装 `scrapling[fetchers]` 全家桶**（playwright/patchright/browserforge/curl_cffi/msgspec 等，已写进 pyproject）+ `scrapling install` 浏览器二进制；只装裸 scrapling 则 import Fetcher 即崩。**搜索抓取必须走代理** `DITING_FETCH_PROXY=http://127.0.0.1:7890`（直连 DDG 被墙，run-lens.sh 已设；StealthyFetcher 抓国内反爬站不走此代理、直连即可）。MacBook 直连、不设此变量

## 🔧 部署工作流（开发 MacBook → 运行 Mac Studio）

改代码在 MacBook，跑在 Mac Studio。改完同步过去：

```bash
# 1) MacBook：改代码 + 测试 + commit/push
cd /Users/<dev-user>/diting-radar
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
git add -A && git commit -m "..." && git push

# 2) 同步到 Mac Studio（排除 venv/日志）
rsync -av --exclude '.venv' --exclude 'state/cron-*.log' src/ scripts/ pyproject.toml macstudio:~/diting-radar/

# 3) 如改了依赖：Mac Studio 重装；如改了 plist：重装 launchd（plist 路径须 /Users/<run-user>）
ssh macstudio 'cd ~/diting-radar && export PATH=$HOME/.local/bin:$PATH && uv pip install --python .venv/bin/python -e .'
ssh macstudio 'cd ~/diting-radar && bash scripts/install-launchd.sh'

# 4) 立刻手动触发验证
ssh macstudio 'bash -l -c "cd ~/diting-radar && bash scripts/run-lens.sh research; tail -15 state/cron-research.log"'
```

> ⚠️ Mac Studio 的 `config.yaml` 和 `scripts/run-lens.sh` 是迁移时定制的（路径 <run-user>、key 读本地 openclaw、设 DITING_FETCH_PROXY）。**rsync 同步代码时别拿 MacBook 版覆盖这两个文件**（上面命令 src/ scripts/ 会覆盖 run-lens.sh —— 改完确认它仍是 Mac Studio 版，或单独维护）。

## ⏰ 自动定时（核心）

| 时间 | 镜头 | 命令 |
|------|------|------|
| 10:00 | 🔭 research | `run-lens.sh research` |
| 14:00 | 🧩 loops | `run-lens.sh loops` |
| 18:00 | 🛰️ trends | `run-lens.sh trends` |
| 20:00 | 🔬 dig（深挖） | `run-lens.sh dig` |
| 11:00 | 📁 project（项目雷达，2026-06-23）| `run-lens.sh project` |
| 09:50/13:50/17:50/19:50 | 🔄 prefetch | `prefetch-vault.py`（每个镜头前把 iCloud「影子」拉回本地）|

每个镜头 job 跑 `scripts/run-lens.sh <lens>`（在 Mac Studio）：从本地 `~/.openclaw/openclaw.json` 读 DeepSeek key（不依赖 ssh），设 `DITING_FETCH_PROXY` 让搜索抓取走代理，**`export PATH=/opt/homebrew/bin:$PATH` 让 launchd 找得到 lark-cli/node**（否则飞书静默发不出，2026-06-19 踩坑），跑 `.venv/bin/python -m diting run --lens <lens>`，日志写 `state/cron-<lens>.log`。另有 `ai.diting.prefetch` 每天 4 次（赶在镜头前 10 分钟）把 iCloud 上变成「影子」(dataless) 的笔记拉回本地，防 research 读取卡死（2026-06-19 加）。

> **另有 MacBook 端定时** `ai.diting.statussync`（登录即推 RunAtLoad + 开着时每 6h 推一次 StartInterval，不挑固定时间，避开睡觉/合盖时段；睡眠时不推、唤醒补推）：跑 `scripts/sync-status-to-studio.sh`，把 MacBook 各项目仓库的 STATUS/ONBOARDING 推到 Mac Studio `~/project-status/` 供谛听读（兴趣信号，谛听第二天读即可）。这是**唯一还留在 MacBook 的 diting 定时**，MacBook→Studio 单推。装：`launchctl load -w ~/Library/LaunchAgents/ai.diting.statussync.plist`。

## 🏗️ 关键外部服务

| 服务 | 地址 | 用途 |
|------|------|------|
| DeepSeek V4 Pro | `https://api.deepseek.com/v1`（model `deepseek-v4-pro`） | 全程 LLM（蒸馏/查询/合成） |
| searxng | `http://localhost:8080`（Mac Studio 没装）| 元搜索；空了走 DDG 兜底（DDG 经 `DITING_FETCH_PROXY=127.0.0.1:7890` 出墙）|
| 飞书 lark-cli | 系统 `/opt/homebrew/bin/lark-cli`（app `cli_REDACTED`/luxury-path4）| 投递（皇后的小跟班 bot，`--as bot`，纯密钥换租户令牌无需 user 登录）|
| Obsidian Inbox | `…/iCloud~md~obsidian/Documents/claude/Inbox` | 投递存档 |

## 🧱 技术栈

- Python 3.11（用全路径 framework python，见禁忌）
- httpx（HTTP）/ pyyaml（配置）/ sqlite3（去重库）/ trafilatura（正文抽取，依赖 `lxml_html_clean`）/ scrapling（抓正文 + DuckDuckGo 兜底搜索；**必须 `scrapling[fetchers]` 全家桶**才装全 Fetcher/StealthyFetcher 依赖；**隐身 `StealthyFetcher` 已启用**——`scrapling install` 装浏览器二进制后反爬域知乎/CSDN 能抓）/ pytest（91 测试）
- DeepSeek V4 Pro（OpenAI 兼容）

## 🗂️ 代码地图

```
diting-radar/
├── src/diting/
│   ├── config.py          # 配置加载（frozen Config）
│   ├── models.py          # frozen dataclass：SignalItem/Interests/Candidate/RankedItem/Report
│   ├── state.py           # StateStore：pushed.db(去重) / interest_profile.yaml(关注清单) / versions.json(版本快照)
│   ├── llm.py             # DeepSeekClient（complete / complete_json）
│   ├── signal/
│   │   ├── obsidian.py     # 读最近会话记录 + 高价值项目目录近期文档(collect_documents)
│   │   ├── distill.py      # DeepSeek 蒸出 Interests
│   │   ├── profile.py      # 关注清单 seed + fatten（含 repos）
│   │   └── dig_topics.py    # dig 选题（想挖清单优先/兴趣兜底/去重/无题 None）
│   ├── query.py           # 查询生成（research / loops 镜头 prompt）
│   ├── sources/           # arxiv / hackernews / github / websearch / github_releases / fetch(scrapling 抓取内核：fetch_text 抓正文 + search_engine DDG 兜底)
│   ├── crawl.py           # 爬取编排（多源合并 + URL 去重 + enrich_bodies top-N 抓正文）
│   ├── novelty.py         # filter_unpushed(跨天去重) + judge_novelty(新颖度)
│   ├── synthesize.py      # 合成 Report（带"为何重要"，空则诚实，lens-aware）
│   ├── dig.py             # 🔬 dig 深挖镜头：run_dig 选题→搜→抓正文→synthesize_dig 综合长资料（独立入口，不复用 run_report）
│   ├── project_radar.py   # 📁 项目雷达镜头(2026-06-23)：detect_changed_projects + run_project_radar，按项目源头记账(配 signal/project_signal.py 读STATUS+算hash、deliver/project_out.py 写 谛听项目情报/<slug>.md、novelty.filter_unpushed_project per-project去重)
│   ├── deliver/
│   │   ├── obsidian_out.py # 追加到 Inbox 当天笔记
│   │   ├── feishu.py       # lark-cli --as bot 发飞书（情报 + dig 短通知）
│   │   └── dig_out.py      # dig 长资料写 Obsidian 谛听深挖/(reference-manual)
│   ├── runner.py          # run_report 编排 + _collect_candidates(分流 research/loops/trends)
│   └── __main__.py        # CLI：run --lens(research/loops/trends/dig) / seed-profile
├── scripts/               # run-lens.sh(含 PATH 补丁) / prefetch-vault.py(拉回 iCloud 影子) / install-launchd.sh / launchd/*.plist / deploy.sh
├── docs/superpowers/      # specs(设计) + plans(v1/v2 计划)
├── config.example.yaml    # 脱敏示例（入库）
├── config.yaml            # 真配置（gitignore）
└── state/                 # gitignore：pushed.db / interest_profile.yaml / versions.json / cron-*.log
```

## 🧪 检查健康

```bash
# launchd 4 任务在不在（在 Mac Studio 上看）
ssh macstudio 'launchctl list | grep diting'
# 全套测试（MacBook 开发机）
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
# 最近自动跑的结果（Mac Studio）
ssh macstudio 'tail -10 ~/diting-radar/state/cron-research.log ~/diting-radar/state/cron-dig.log'
```

## 🔑 敏感文件（已 gitignore，永不入库）

- `config.yaml` — 含真实路径/open_id
- `~/.diting.env` — `DEEPSEEK_API_KEY`（在 $HOME，不在仓库）
- `state/` — 运行时数据 + 日志

DeepSeek key 权威来源：macstudio `~/.openclaw/openclaw.json` 的 `providers.deepseek.apiKey`。全局密钥见 `~/.claude/projects/*/memory/credentials.md`。

## 📚 权威文档位置

| 文档 | 路径 | 用途 |
|------|------|------|
| 开场手册 | `ONBOARDING.md` | 新 Claude 进门 |
| 下班手册 | `OFFBOARDING.md` | 收尾 9 步 checklist |
| 当前进度 | `STATUS.md` | 进度快照 + 下次第一件事 |
| 运维救命 | `RUNBOOK.md` | 没发情报/换 key/重建 |
| 设计文档 | `docs/superpowers/specs/2026-06-18-diting-radar-design.md` | 完整设计 |
| 记忆 | Qdrant v3 搜 "谛听" + `~/.claude/.../memory/diting-radar.md` | 项目记忆 |
