# 谛听 · 项目雷达（per-project 情报）→ onboard 自动接入 设计文档

> 日期：2026-06-23
> 状态：设计已确认，待写实现计划
> 一句话：让谛听针对每个项目单独跑、产出"项目专属情报流"，并在 `/<proj>-onboard` 时自动读出来。

---

## 1. 背景与问题

谛听现在每天产出的情报是**按日期堆、所有项目+兴趣混在一起**的：

- 每日短情报 → `Inbox/YYYY-MM-DD 谛听情报.md`
- 深挖长资料 → `谛听深挖/YYYY-MM-DD …​.md`

硬盘上**没有"专属某个项目的情报"**——情报没有项目标签。用户希望：打开某个项目（如 `/ytst-onboard`）时，Claude 能自动读到"谛听最近替这个项目盯到的料"。

**核心障碍**：谛听现在的流水线把所有信号（会话记录 + 各项目 STATUS + 多个兴趣目录）**搅成一锅**一起蒸馏，到产出那一步，"这条来自哪个项目"的源头标签已经在蒸馏步丢失。

**有利条件**：用户的各项目 STATUS/ONBOARDING **本来就是一个项目一个文件**，由 MacBook 的 `ai.diting.statussync` 定时推到 Mac Studio 的 `~/project-status/`（扁平命名，如 `macbook-ytst-STATUS.md`）。所以"按项目来源记账"是天然可行的。

---

## 2. 目标与非目标

### 目标
1. 新增"项目雷达"镜头：**一个项目一份**地跑，只拿该项目自己的 STATUS/ONBOARDING 当线索 → 爬 → 合成带"为何对这个项目重要"的情报（**源头记账**，标签 100% 准）。
2. 产出落成**每个项目一份**的情报文件，`/<proj>-onboard` 时自动读取并汇报。
3. **只在某项目 STATUS 改过时**才给它跑，省爬虫/LLM 开销。
4. 精准（只汇报与该项目直接相关的），不动现有任何功能。

### 非目标
- ❌ 不改现有 4 镜头、飞书推送、每日混合情报。项目雷达是**新增的第 5 条腿**。
- ❌ 不做"事后把混合情报分类到项目"（用户明确要源头记账，不要猜）。
- ❌ 不做 onboard 时现场触发爬取（会拖慢 onboard、跨机器复杂）。改为**预先跑好、onboard 只读**。
- ❌ 不做反馈闭环（点有用/没用自学习）——那是 v3 的事，本设计不含。

---

## 3. 架构总览

```
~/project-status/macbook-<proj>-STATUS.md   (各项目 STATUS，已由 statussync 推来)
        │
        ▼
  变更检测 detect_changed_projects()         ← 对比 state/project_radar.json 里的 hash
        │  (只留 STATUS 改过的项目)
        ▼
  for each changed proj:
     collect_project_signal(proj)            ← 只读该项目自己的 STATUS/ONBOARDING
        ▼ distill（蒸馏出"这个项目在追啥/卡在哪"）
        ▼ generate_queries（沿用现有查询生成）
        ▼ crawl（沿用现有多源爬取 + 抓正文）
        ▼ per-project 去重（key = slug + url，保证项目流完整）
        ▼ synthesize（合成带"为何对本项目重要"）
        ▼
  write_project_intel(proj, report)          ← prepend 到 谛听项目情报/<slug>.md
        ▼
  投递成功 → 更新该项目 STATUS hash（投递失败不更新，下次重试）

（另一侧）/<proj>-onboard → 读 谛听项目情报/<slug>.md 最上面最近几条 → 汇报
```

**复用现有零件**：`llm.py` / `query.py` / `crawl.py` / `synthesize.py` / `sources/*`。
**新增零件**：项目雷达编排 + 项目信号收集 + 项目投递 + state 扩展 + config 扩展 + 新 launchd。

---

## 4. 组件设计

每个组件回答：做什么 / 怎么用 / 依赖谁。

### 4.1 `detect_changed_projects()` （变更检测）
- **做什么**：扫 `~/project-status/`，按 config 的项目清单找各项目的 STATUS 文件，算内容 hash，和 `state/project_radar.json` 里记录的上次 hash 对比，返回"改过的（或从没跑过的）"项目 slug 列表。
- **怎么用**：项目雷达入口先调它，拿到要跑的项目清单（通常 1-3 个，多数项目当天没动）。
- **依赖**：`config.project_radar.projects`（slug + match）、`StateStore` 的 hash 读写、`~/project-status/`。

### 4.2 `collect_project_signal(proj)` （项目信号收集）
- **做什么**：读该项目对应的 STATUS/ONBOARDING 文本（在 `~/project-status/` 里 match 到的文件），返回 `SignalItem` 列表。**只读这一个项目的文档**——这是"源头记账"的关键，绝不掺别的项目或会话记录。
- **怎么用**：拿到的信号喂给现有 `distill_interests()`。
- **依赖**：`models.SignalItem`、文件读取（沿用 `obsidian.py` 的守护线程超时容错思路，但读的是本地 `~/project-status/` 非 iCloud，风险低）。

### 4.3 `run_project_radar()` （编排，新模块 `src/diting/project_radar.py`）
- **做什么**：项目雷达的主入口。流程：`detect_changed_projects()` → 对每个改过的项目：`collect_project_signal` → `distill` → `generate_queries` → `crawl` → per-project 去重 → `synthesize` → `write_project_intel` → 投递成功后更新该项目 hash。
- **怎么用**：`__main__` 的 `--lens project` 调它；launchd 每天定时触发。
- **依赖**：上面所有组件 + 现有 `llm/query/crawl/synthesize`。
- **错误隔离**：单个项目爬/合成失败 → 该项目跳过、**不更新 hash**（下次重试），不影响其他项目。无变更项目 → 整体 no-op，日志记"无变更，跳过"。

### 4.4 `write_project_intel(proj, report)` （项目投递，新模块 `src/diting/deliver/project_out.py`）
- **做什么**：把该项目本轮情报 **prepend（插到最上面）** 到 `谛听项目情报/<slug>.md`。首次创建时写 Obsidian frontmatter（5 字段）；之后每次把新的"## YYYY-MM-DD"小节插在 frontmatter 之后、旧内容之前，并更新 `last_updated`。**空报告不写**（precision-first）。
- **怎么用**：`run_project_radar` 在 synthesize 出非空报告后调用；返回是否成功（决定要不要更新 hash）。
- **依赖**：`config.project_radar.output_dir`、文件写入（沿用现有写 Inbox 的 iCloud 容错方式）。

### 4.5 `StateStore` 扩展（`src/diting/state.py`）
- 新增 `get_status_hash(slug)` / `set_status_hash(slug, hash)`：读写各项目 STATUS 上次跑时的 hash（存 `state/project_radar.json`）。
- 新增 `is_project_pushed(slug, url)` / `mark_project_pushed(slug, url)`：**per-project 去重**（key = slug+url），存在 `pushed.db` 里**一张新表 `project_pushed(slug, url)`**（复用 sqlite，但与全局去重表分开，互不影响）——见 §6。
- **存储分工**：各项目 STATUS 的 hash → `state/project_radar.json`（小）；per-project 已推 url → `pushed.db` 的 `project_pushed` 表（沿用 sqlite，url 量大也扛得住）。

---

## 5. 项目名映射（slug ↔ STATUS 文件）

`~/project-status/` 的文件名由 statussync 决定（如 `macbook-ytst-STATUS.md`），其中的名字可能跟 onboard skill 的缩写**不完全一致**（例：仓库 `luxury-bag-copilot` vs skill `lbc`）。所以需要一张**显式映射表**，放进 config，由用户维护（项目数少，可接受）：

```yaml
project_radar:
  enabled: true
  output_dir: "/Users/<run-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/谛听项目情报"
  status_dir: "/Users/<run-user>/project-status"
  projects:
    - slug: ytst          # = onboard skill 缩写 + 情报文件名 谛听项目情报/ytst.md
      match: "ytst"       # 用来在 status_dir 里 match STATUS/ONBOARDING 文件的子串
    - slug: lbc
      match: "luxury-bag-copilot"
    - slug: kcgl
      match: "kcgl"
    # …用户按需增减
```

- `slug`：**唯一权威名**，同时作为情报文件名 `谛听项目情报/<slug>.md` 和 onboard skill 读取的名字。
- `match`：在 `status_dir` 里找该项目的 STATUS/ONBOARDING 文件用的子串（找 `*<match>*STATUS*.md` 和 `*<match>*ONBOARDING*.md`）。
- **约束**：onboard skill 里读取的文件名必须用对应的 `slug`。两边对齐由这张表保证。
- `projects` 这张表**同时是参与雷达的白名单**——没列进来的 STATUS 文件不跑（避免给无关文件浪费爬虫）。

---

## 6. 去重策略（关键决策）

现有全局 `pushed.db` 做跨镜头去重。**项目雷达不共用它**，理由：若共用，一条情报被别的镜头（如 research）先推过，项目雷达再爬到同一条就被全局去重挡掉 → **项目流不完整、会漏**。

**决策**：项目雷达用**独立的 per-project 去重**，key = `(slug, url)`，存在 `pushed.db` 的新表 `project_pushed(slug, url)` 里（复用 sqlite，与全局去重表分开）。

- 好处：每个项目的情报流是**完整**的，不会被其他镜头"偷走"那条。
- 代价：同一条情报可能**既出现在每日混合情报、又出现在项目流**。可接受——两者用途不同（一个是每日扫一眼，一个是项目专属档案）。
- 项目流**内部仍跨天去重**（同 slug 不重复同 url）。

---

## 7. 输出文件格式（`谛听项目情报/<slug>.md`）

文件在 Obsidian vault 里，**必须遵守 vault 文档纪律**：带 5 字段 frontmatter，放对子目录（新建一级目录 `谛听项目情报/`，需在 vault 根 README 加一行）。

```markdown
---
title: 谛听项目情报 · ytst
type: progress-log
status: active
created: 2026-06-23
last_updated: 2026-06-23
---

# 谛听项目情报 · ytst

> 谛听「项目雷达」镜头自动产出 · 只收和本项目直接相关的料 · 最新在最上

## 2026-06-23
- [标题](https://…) — 为什么对 ytst 重要（一句话）
- [标题](https://…) — …

## 2026-06-20
- …（更早的留在下面）
```

- 每次有新情报：把新的 `## YYYY-MM-DD` 小节**插在 frontmatter 之后、旧内容之前**（最新在最上），并更新 `last_updated`。
- **空运行不写**（precision-first）——没新料的那天文件不动。
- `type` 用 `progress-log`（滚动追加日志性质，符合 vault 已有 type 字符串）。

---

## 8. onboard 接入

### 8.1 改每个 `<proj>-onboard` SKILL.md
在现有"扫 Obsidian 最近文档"步**旁边新增一步**（编号顺延，如第 3.5 步）：

> **读谛听项目情报**：Read `谛听项目情报/<slug>.md`，只看**最上面前 2 个日期小节（约最近 2 周）**（不读整篇旧档），汇报"谛听最近替本项目盯到这些料"。文件不存在 → 跳过，汇报"暂无谛听项目情报"。

汇报时把这块并入第 4 步的状态总结，作为单独一节。

### 8.2 改 setup-kit 的 onboard 模板
同步把这一步加进 `~/.claude/skills/setup-kit/`（及 setup-kit-pro）的 onboard 模板，**以后新建项目自带**这能力。

### 8.3 受影响的现有 onboard skills
`~/.claude/skills/*-onboard/SKILL.md`：ytst / lbc / kcgl / infpick / diting / cpsk / lp4 / xlyth / xianyu 等。
- **第一版**：只改 `config.project_radar.projects` 里列了的活跃项目对应的 onboard skill。
- 其余 onboard skill 随用随改（加同样一步即可）。

---

## 9. 定时与运行

- 新增 launchd `ai.diting.project`，每天 **11:00**（research 10:00 之后），`scripts/launchd/` 加 plist，并入 `install-launchd.sh`。Mac Studio 共变 **6 个 launchd**（4 镜头 + prefetch + project）。
- `scripts/run-lens.sh` 加 `project` 分支：`.venv/bin/python -m diting run --lens project`（继承现有 PATH 补丁 + `DITING_FETCH_PROXY` 代理设置）。
- `src/diting/__main__.py` 的 `--lens` 增加 `project` 选项 → 调 `run_project_radar()`。
- 读的是本地 `~/project-status/`（非 iCloud，无影子卡死风险）；写 vault 沿用现有 Inbox 写法的 iCloud 容错。

---

## 10. 错误处理与边界

| 情况 | 行为 |
|------|------|
| 某项目爬/合成失败 | 该项目跳过、**不更新 hash**（下次重试），不影响其他项目 |
| LLM 整体失败 | 该项目本轮不产出（降级，不硬凑） |
| `~/project-status/` 不存在或空 | 整镜头 no-op |
| 无 STATUS 变更的项目 | 跳过（日志记"无变更，跳过"） |
| 合成结果为空 | 不写文件、不更新 hash（precision-first） |
| onboard 时情报文件不存在 | 跳过，汇报"暂无谛听项目情报" |

---

## 11. 测试计划（TDD）

- `detect_changed_projects`：hash 变了→入选 / 没变→跳过 / 新项目（无记录）→入选 / STATUS 文件缺失→跳过。
- `collect_project_signal`：读到 STATUS 文本 / 文件缺失返空 / 只读该项目不掺别的。
- per-project 去重：同 `(slug,url)` 第二次被挡 / 不同 slug 同 url **不互相挡**。
- `write_project_intel`：首次建带 frontmatter / 再次 prepend 保持 frontmatter 在顶 + `last_updated` 更新 / 空报告不写。
- `run_project_radar` 端到端（mock LLM/sources）：changed 项目产出、未变项目跳过、**投递成功才更新 hash**。
- slug/match 映射：`match` 子串能在 `status_dir` 找到对应 STATUS/ONBOARDING。
- config 解析：`project_radar` 字段默认值 / 读取 / `enabled=false` 时镜头不跑。

---

## 12. 影响文件清单

### diting-radar（新增/改）
- `src/diting/project_radar.py`（新，编排）
- `src/diting/deliver/project_out.py`（新，投递）
- `src/diting/signal/project_signal.py`（新，或并入 `obsidian.py`：`collect_project_signal`）
- `src/diting/state.py`（扩展 hash + per-proj 去重）
- `src/diting/config.py`（`project_radar` 配置）
- `src/diting/__main__.py`（`--lens project`）
- `scripts/run-lens.sh`（`project` 分支 ⚠️ Mac Studio 是定制版，别被 rsync 覆盖）
- `scripts/launchd/ai.diting.project.plist`（新）+ `scripts/install-launchd.sh`
- `config.example.yaml`（加 `project_radar` 示例）+ Mac Studio 的 `config.yaml`（填真实 projects 表）
- `tests/test_project_radar.py` 等

### 全局 skills（改）
- `~/.claude/skills/<proj>-onboard/SKILL.md`（加一步，先改活跃项目）
- `~/.claude/skills/setup-kit/`（+ setup-kit-pro）onboard 模板

### Obsidian vault
- 新建一级目录 `谛听项目情报/` → 在 vault 根 `README.md` 的「📁 一级目录」表加一行。

---

## 13. 部署流程

1. **MacBook**：改代码 + `pytest` 全绿 + commit/push。
2. `rsync src/ scripts/ pyproject.toml macstudio:~/diting-radar/`（无新依赖，不用重装；**确认 run-lens.sh 仍是 Mac Studio 定制版**）。
3. **Mac Studio**：`config.yaml` 加 `project_radar.projects` 真实表 + `bash scripts/install-launchd.sh` 装新 launchd。
4. `launchctl kickstart -k gui/$(id -u)/ai.diting.project` 手动触发验证，看 `state/cron-project.log` + vault 里 `谛听项目情报/<slug>.md` 是否生成。
5. onboard skills 在 `~/.claude/` 直接改（全局生效）。

---

## 14. 开放问题与风险

- **slug/match 映射要人工维护一张表**：项目数少，可接受；漏配某项目 = 它没有项目雷达（不报错，静默不跑）。
- **project-status 同步有延迟**：MacBook 每 6h 推一次，项目雷达看到的 STATUS 可能不是当下最新——对 onboard 用途够了（STATUS 变化慢）。
- **同一条情报可能在每日情报和项目流都出现**：独立去重的代价，接受（用途不同）。
- **第一版只覆盖 `~/project-status/` 里有 STATUS 的项目**：Mac Mini 上的项目暂不覆盖（与现状一致）。
- **未来可选**：项目流加"过期清理"（只留最近 N 天）；接 v3 反馈闭环（点有用/没用调该项目关注清单）。

---

## 15. 不做什么（YAGNI 提醒）

- 不做配置 UI、不做 per-project 阈值微调、不做事后分类兜底、不做 onboard 现场触发。
- 第一版项目流**只追加不清理**（文件增长慢，空运行不写，短期不会臃肿）。

