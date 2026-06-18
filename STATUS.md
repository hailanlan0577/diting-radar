# 项目当前状态

> 最后更新：2026-06-18
> 新 Claude 进门先读 `CLAUDE.md`（地形 + 部署），再读本文件（进度 + 下一步）。

## 🎯 一句话

谛听 v1+v2 全部上线，三镜头 + launchd 三时段定时已激活、自动跑着；飞书+Obsidian 双通道实测送达。**无硬阻塞**，下一步是 v3 打磨/增强。

## 📊 Phase 完成度

### Phase 0 — 基础设施 ✅

- Python 包结构 + 53 个 TDD 测试全绿
- GitHub 私有仓 `hailanlan0577/diting-radar`，main 分支
- launchd 三时段定时已激活

### Phase 1 — 引擎 + 🔭 科研雷达 (v1) ✅

- 6 段流水线：信号(Obsidian 会话记录)→蒸馏(DeepSeek)→查询生成→爬(arXiv/HN/GitHub/searxng)→去重+新颖度→合成(带"为何重要")→飞书+Obsidian 投递
- 15 个 TDD 任务 + opus 全分支审查，真跑验收通过（爬出 7 条精准情报）
- DeepSeek 故障会降级告警；空报告不刷飞书（precision-first）

**当前规模**：53 测试，单进程，全程 DeepSeek V4 Pro

### Phase 2 — 三镜头 + 定时 (v2) ✅

- 🧩 loops 镜头（悬而未决 + 反方/唱反调）
- 🛰️ trends 镜头（GitHub release 版本哨兵 + versions.json diff，投递成功后才推进快照防丢新版）
- launchd：10:00 research / 14:00 loops / 18:00 trends，从 `~/.diting.env` 读 key 不依赖 ssh
- opus 全分支审查抓出并修了 trends 快照写太早的 Critical bug

### Phase 3 — v3 增强 ⏳ 未启动

- 反馈闭环（点有用/没用 → 自学习调关注清单/阈值）
- 中文生态源（知乎/公众号技术帖）
- 二奢生意情报镜头（另一台引擎）
- searxng 走代理修复

---

## 🔴 当前阻塞

**无硬阻塞**——谛听已自动运行。以下是可选打磨项（非阻塞）。

---

## 🐛 其他已知小问题

1. **`来源:?`** — synthesize 时模型回的 URL 跟候选 URL 有细微差异（如末尾斜杠）→ 没匹配到来源标签，回退成 `?`。cosmetic，修法是加模糊 URL 匹配。
2. **searxng/websearch 常空** — searxng 上游引擎可能要走代理；目前 arXiv/HN/GitHub 三家已扛起来，websearch 是 bonus。
3. **首次 trends 跑会把当前所有版本当"新版"** — 建基线行为，之后只报真·新版。
4. **fatten_profile 把 distill 出的实体一股脑塞进 tools/topics** — profile 会越长越大（已观察到），不影响功能，v3 可加去噪。

---

## 📝 2026-06-18 做了什么

### 2026-06-18（阶段二 dig 自动深挖镜头上线 ✅）

1. ✅ **新增 dig 自动深挖镜头**：每天 20:00 自动挑一个话题（想挖清单 `state/dig_queue.yaml` 优先 → 空了从兴趣自动选 → 已挖去重 → 无题跳过），多角度搜 + 深抓正文 → DeepSeek 综合成结构化中文长资料 → 落 Obsidian `谛听深挖/`（reference-manual）+ 飞书短通知。复用阶段一抓取内核，走独立 `run_dig` 入口。
2. ✅ **10 任务 TDD（subagent-driven）+ opus 全分支审查 + 真跑验收**：91 测试全绿，真跑《scrapling 反爬最佳实践》抓 12 篇 → 90 行长资料（5 小节齐全）+ 飞书通知，scrapling 日志干净。已合并 main + push。
3. ✅ **launchd 现 4 时段**：10 research / 14 loops / 18 trends / 20 dig。
4. 📝 **想挖清单用法**：往 `state/dig_queue.yaml` 写 `- "话题"` 即优先深挖；不写则自动从你最近兴趣选题。第一版不含 gh 扒代码仓（留 v2）。

### 2026-06-18（scrapling 网搜深化 · 阶段一上线 ✅）

1. ✅ **新增 scrapling 抓取内核** `sources/fetch.py`：`fetch_text` 抓网页正文 + `search_engine`（DuckDuckGo HTML 兜底搜索），失败一律降级返空（precision-first）。
2. ✅ **日常 research/loops 网搜增强**：searxng 空了自动切 DDG 兜底；候选 top-5 真抓正文喂大模型；修了 `来源:?` 回退（URL 规范化匹配）。
3. ✅ **scrapling 当库集成**（非 MCP——谛听是无人值守进程调不到 MCP）：装入 framework python。⚠️`StealthyFetcher` 因 browserforge 本机暂不可用→反爬域(知乎/CSDN)抓不到就跳过；scrapling 日志已静音（`_quiet_scrapling()` 在 import 后压回 ERROR），不污染 cron 日志。
4. ✅ **11 任务 TDD（subagent-driven）+ opus 全分支审查 + 真跑验收**：73 测试全绿，真跑爬出 3-7 条情报、DDG 兜底+抓正文生效、日志干净。已合并 main 并 push。
5. ⏳ **阶段二（dig 自动深挖镜头）待做**——共用本阶段抓取内核，每天选题深挖（清单优先+自动选题）产出 Obsidian 长资料 + 飞书短通知，20:00 定时。设计见 `docs/superpowers/specs/2026-06-18-diting-scrapling-deepdig-design.md`。

### 2026-06-18（v1+v2 上线）

1. ✅ **从脑洞到上线一气呵成** — brainstorm → 设计 → v1 计划(15 TDD 任务·子代理实现+审查) → opus 全分支审查 → 合并 → 真跑验收 → v2(loops/trends/launchd) → 上自动
2. ✅ **飞书+Obsidian 双通道打通** — 飞书走"皇后的小跟班"机器人(`--as bot`)，open_id 已填 config
3. ✅ **launchd 三时段定时激活** — 10/14/18 三镜头，本机自动跑
4. ✅ **救命手册 pro 套件就位** — ONBOARDING/CLAUDE/STATUS/RUNBOOK/OFFBOARDING + /diting-onboard /diting-offboard skill
5. ⚠️ **真跑暴露并修了 4 个真 bug** — arXiv 要 https / 查询要短关键词 / lxml_html_clean 依赖 / 飞书 --as bot
6. ⚠️ **trends 快照 Critical** — 原本检测即写快照→投递失败就丢新版；改成投递成功后才推进

---

## 🧭 下一步建议顺序

> 顺序是参考，用户拍板。

1. **观察几天自动跑的效果** — 看飞书每天三条情报质量如何，再决定调啥
2. **打磨项 B**（小）— 修 `来源:?` + searxng 代理
3. **v3 反馈闭环**（中）— 点有用/没用自学习

---

## 🔗 快速链接

- GitHub: https://github.com/hailanlan0577/diting-radar （private）
- 设计文档：`docs/superpowers/specs/2026-06-18-diting-radar-design.md`
- 记忆系统：Qdrant v3 搜 "谛听" / file-based `~/.claude/projects/-Users-<dev-user>/memory/diting-radar.md`
- 密钥表：`~/.claude/projects/*/memory/credentials.md`

---

## 🎯 下次进来第一件事

**🚚 把谛听迁移到 Mac Studio**（用户拍板 2026-06-18：MacBook 会合盖/关机，定点任务 10/14/18/20 漏跑；Mac Studio 24h 开机才对）。按 runbook 一步步做：

→ **`docs/superpowers/plans/2026-06-18-diting-migrate-to-macstudio.md`**（8 步 A-H，Mac Studio 环境已 ssh 核实：python3.11/uv/git/同 iCloud vault/openclaw key 都就绪；缺 lark-cli/searxng）

**关键**：唯一卡用户的是步骤 D（飞书 lark-cli 登录授权）——迁移前先跟用户约好时间。迁完按计划末尾改 ONBOARDING/CLAUDE/Obsidian 手册的"部署目标"为 Mac Studio。

⚠️ 迁移完成前 **MacBook 这台仍在跑**（4 个 launchd 还活着），别提前停；步骤 G 才停。

---

阶段一/二已上线（scrapling 网搜深化 + dig 深挖镜头，91 测试，合并 main）。迁移后可选打磨：dig 加 gh 扒代码仓(v2) / searxng 代理 / 修隐身抓取(Mac Studio 上 browserforge 可能本就好的)。
