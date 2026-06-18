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

### 2026-06-18（最新）

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

**先确认自动任务在正常跑**，再问用户要不要动 v3：

```bash
launchctl list | grep diting          # 三任务应都在
tail -5 ~/diting-radar/state/cron-research.log   # 看最近一次自动跑结果
```

如果用户想验证某镜头，手动跑：`bash ~/diting-radar/scripts/run-lens.sh research`（research/loops/trends 任选）。
