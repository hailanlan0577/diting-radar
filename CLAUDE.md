# 谛听 · 个人技术情报雷达 — Claude 操作手册

> **如果用户明确让你"继续项目"或贴了 ONBOARDING 口令，优先读 `ONBOARDING.md`。**
>
> 新 Claude 进门先读这份，30 秒掌握地形。详细进度见 `STATUS.md`，完整设计见 `docs/superpowers/specs/2026-06-18-diting-radar-design.md`。

## 一句话

谛听：每天读你做过的事 → DeepSeek V4 Pro 蒸出兴趣 → 爬全网 → 砍已知 → 合成"为何重要"的技术情报 → 飞书 + Obsidian 双通道。Python 3.11，跑本机 launchd，服务用户本人。

## 🔴 地理：源码在哪，部署在哪

| 位置 | 角色 | 路径 |
|------|------|------|
| **本地 MacBook** | 源码主分支（唯一） | `/Users/<dev-user>/diting-radar` |
| **GitHub** | 远程备份 | `https://github.com/hailanlan0577/diting-radar`（private） |
| **部署目标** | 本机 launchd 定时 | `~/Library/LaunchAgents/ai.diting.{research,loops,trends}.plist` |

**禁忌：**
- ❌ 不要用裸 `python`（alias 到 framework，不是 venv）—— 用全路径 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3` 或 `python -m pip`
- ❌ 飞书发消息不要漏 `--as bot`（否则进看不到的自聊）
- ❌ 不要把 `config.yaml` / `~/.diting.env` 推 git

## 🔧 "部署"工作流（本机 launchd，无远程）

谛听跑在本机，没有远程服务器。"部署"= 装/重装 launchd 定时 + 跑测试。

```bash
cd /Users/<dev-user>/diting-radar
# 跑测试 + 重装定时
bash scripts/deploy.sh
# 只重装 launchd（改了 plist/脚本）
bash scripts/deploy.sh --restart
# 立刻手动触发一个镜头（验证）
bash scripts/run-lens.sh research
```

## ⏰ 自动定时（核心）

| 时间 | 镜头 | 命令 |
|------|------|------|
| 10:00 | 🔭 research | `run-lens.sh research` |
| 14:00 | 🧩 loops | `run-lens.sh loops` |
| 18:00 | 🛰️ trends | `run-lens.sh trends` |

每个 job 跑 `scripts/run-lens.sh <lens>`：从 `~/.diting.env`(chmod600，存 `DEEPSEEK_API_KEY`)读 key（不依赖 ssh），跑 `python -m diting run --lens <lens>`，日志写 `state/cron-<lens>.log`。

## 🏗️ 关键外部服务

| 服务 | 地址 | 用途 |
|------|------|------|
| DeepSeek V4 Pro | `https://api.deepseek.com/v1`（model `deepseek-v4-pro`） | 全程 LLM（蒸馏/查询/合成） |
| searxng | `http://localhost:8080` | 元搜索（上游引擎可能要代理，目前 websearch 常空） |
| 飞书 lark-cli | 系统 `/opt/homebrew/bin/lark-cli` | 投递（皇后的小跟班 bot，`--as bot`） |
| Obsidian Inbox | `…/iCloud~md~obsidian/Documents/claude/Inbox` | 投递存档 |

## 🧱 技术栈

- Python 3.11（用全路径 framework python，见禁忌）
- httpx（HTTP）/ pyyaml（配置）/ sqlite3（去重库）/ trafilatura（正文抽取，依赖 `lxml_html_clean`）/ pytest（53 测试）
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
│   │   ├── obsidian.py     # 读最近会话记录
│   │   ├── distill.py      # DeepSeek 蒸出 Interests
│   │   └── profile.py      # 关注清单 seed + fatten（含 repos）
│   ├── query.py           # 查询生成（research / loops 镜头 prompt）
│   ├── sources/           # arxiv / hackernews / github / websearch / github_releases(版本哨兵)
│   ├── crawl.py           # 爬取编排（多源合并 + URL 去重）
│   ├── novelty.py         # filter_unpushed(跨天去重) + judge_novelty(新颖度)
│   ├── synthesize.py      # 合成 Report（带"为何重要"，空则诚实，lens-aware）
│   ├── deliver/
│   │   ├── obsidian_out.py # 追加到 Inbox 当天笔记
│   │   └── feishu.py       # lark-cli --as bot 发飞书
│   ├── runner.py          # run_report 编排 + _collect_candidates(分流三镜头)
│   └── __main__.py        # CLI：run --lens / seed-profile --from
├── scripts/               # run-lens.sh / install-launchd.sh / launchd/*.plist / deploy.sh
├── docs/superpowers/      # specs(设计) + plans(v1/v2 计划)
├── config.example.yaml    # 脱敏示例（入库）
├── config.yaml            # 真配置（gitignore）
└── state/                 # gitignore：pushed.db / interest_profile.yaml / versions.json / cron-*.log
```

## 🧪 检查健康

```bash
# launchd 三任务在不在
launchctl list | grep diting
# 全套测试
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
# 最近自动跑的结果
tail -10 state/cron-research.log state/cron-loops.log state/cron-trends.log
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
