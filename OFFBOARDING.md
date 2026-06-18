# 🛑 会话结束前 Claude 必做（收场手册）

> **触发时机**：用户说"存档 / 记录一下 / 今天就到这 / 下班 / 结束 / 窗口快满了 / 写个交接"等任意一句。
>
> **目标**：下一个窗口贴开场口令（读 `ONBOARDING.md`）能**无缝接上**，不丢任何上下文。

## 💡 触发方式（给用户看）

1. **最快** —— 打 `/diting-offboard` 斜杠命令
2. **随口说** —— "下班" / "今天就到这" / "存档" / "窗口快满了"，Claude 会识别关键词自动触发
3. **完整口令** —— 复制下面这段：
   ```
   窗口快满了/今天就到这。
   请按 /Users/<dev-user>/diting-radar/OFFBOARDING.md 的 checklist 执行收尾：
   1. 更新 STATUS.md 今天做了什么
   2. 新坑加进 ONBOARDING.md 禁忌
   3. 未 commit 的代码 commit + push
   4. 改了密钥同步 credentials.md
   5. Qdrant 存一条进度记忆
   6. 告诉我下次进来第一件事做什么
   做完了逐条报告给我。
   ```

---

## ✅ Checklist（Claude 按顺序执行）

### ① 记下今天做了什么 —— 更新 `STATUS.md`

在 `STATUS.md` 的"📝 YYYY-MM-DD 做了什么"段落追加今天这一条目：

- 按时间顺序，每条一句话
- 写**结果**不写过程（"修了 X，结果是 Y"，不写"我试了 A 又试了 B 才发现..."）
- 用 ✅ / ⚠️ / ❌ 标状态
- 失败的事也要记（让下个 Claude 不重复踩坑）

### ② 发现新坑 → 进 `ONBOARDING.md` 禁忌清单

如果今天**踩过坑 / 发现别人容易错**的东西（配置格式、命令副作用、路径陷阱、MCP 工具行为），**立即**加进 `ONBOARDING.md` 的"🚫 N 大禁忌"清单里。

格式：`不要 X，因为 Y（踩坑日期）`

### ③ 改了代码就 git commit + push

```bash
cd <项目路径>
git status --short
# 如果有未提交改动
git add <具体文件>  # 别用 git add .
git commit -m "<type>: <描述>"
git push
```

commit message 规范：`feat:` / `fix:` / `docs:` / `refactor:` / `chore:`

### ④ 改了代码想上线？跑 deploy.sh

```bash
bash scripts/deploy.sh
# 或只重启（改了 config 没改代码）
bash scripts/deploy.sh --restart
```

**验证**：按项目约定（看 RUNBOOK § 7 健康检查）。

### ⑤ 密钥变化同步到 `credentials.md`

如果今天：
- 加了新的第三方服务（改了 config.yaml 加新字段）
- 换了某个 token（密码轮转）
- 新增了某个 webhook

→ 同步到 `~/.claude/projects/*/memory/credentials.md`

**多地 config.yaml 一致性校验**：
```bash
diff <(md5 -q <本地 config>) <(<远程 md5 命令>)
# 无输出 = 一致
```

不一致就同步。

### ⑥ 大变动？更新 `CLAUDE.md` 代码地图

遇到这些情况动 `CLAUDE.md`：
- 加了新包 / 新模块 → 代码地图加一行
- 换了部署方式 → 部署工作流章节更新
- 新增了关键服务端点 → 服务端点表加一行

### ⑦ 记忆系统存一条进度

调用你项目约定的记忆系统（Qdrant / Graphiti / claude-mem 之一）：

```
category: project
tags: 谛听,progress,YYYY-MM-DD
content: "谛听 YYYY-MM-DD 进展：<今天关键结果>。下次第一件事：<X>。当前阻塞：<Y 或 无>。"
```

这条记忆**比 STATUS.md 更精简**，让下个 Claude 搜"谛听 最新"就能命中。

### ⑧ Obsidian 沉淀（可选，仅当今天有实质讨论时跑）

如果今天有**架构决策 / 紧急抢救事件 / 头脑风暴 / 复盘 / 深度学习** 10 轮以上的实质讨论，跑：

```
/save-to-obsidian
```

这个 skill 会自动判断文档类型（ADR / Design Doc / Brainstorm / Retro / Learning），按对应模板填好写进 Obsidian vault。跟第 ⑦ 步的记忆系统互补：记忆是索引（几十字），Obsidian 文档是正文（完整内容）。

**判断阈值：**
- ✅ 适合：架构决策、14 小时级抢救事件、三方案比较、复盘类讨论
- ❌ 跳过：日常 commit、小 bug 修复、"帮我跑下命令"这种操作请求

### ⑨ 最后一步：给下个 Claude 留便条

在 `STATUS.md` 末尾加/更新一节（覆盖上次的便条）：

```markdown
## 🎯 下次进来第一件事

<一句话明确告诉下个 Claude 做什么>

例如：
- "修 X 接着昨天 A 方案，先跑 <具体命令> 看 <什么>"
- "Phase 3 从 internal/xxx/yyy.go 开始"
- "不用改代码，先 <某个动作> 再评估"
```

---

## 最后：逐条报告给用户

按 1-9 步逐条报告**做了什么**：

```
✅ 1. STATUS.md 已更新：追加 YYYY-MM-DD 做了 X/Y/Z
✅ 2. 新坑已加进 ONBOARDING 禁忌：[坑的简述]（或：无新坑）
✅ 3. git 已 commit + push：commit abc1234
✅ 4. 部署已完成（或：无代码改动，跳过）
✅ 5. 密钥已同步（或：无变化，跳过）
✅ 6. CLAUDE.md 代码地图已更新（或：无大变动，跳过）
✅ 7. 记忆已存 [ID: xxxxxxxx]
✅ 8. Obsidian 文档已沉淀：[文档名]（或：无值得沉淀的讨论，跳过）
✅ 9. STATUS.md 末尾便条已留："下次第一件事做 X"

下次新开窗口，贴开场口令或打 /diting-onboard 就能无缝接上。
```

---

## ⚠️ Claude 自检：当前会话需要主动提醒用户下班吗？

**如果你（Claude）感觉到**：
- 开始被提示"context 快满了"
- 正在频繁 summarize 之前的内容
- 上下文里文件引用变得模糊
- 已经连续 30+ 轮对话没有结束

**主动提示用户**：
> "感觉上下文接近满了，要不要我按 OFFBOARDING.md 做一次收尾，让下一个窗口无缝接上？"

等用户确认再执行 checklist。

---

## 🔁 完整会话生命周期

```
开新窗口 → 用户贴 ONBOARDING 口令
   ↓
Claude 读 ONBOARDING.md → 汇报状态
   ↓
用户说做什么 → （干活...）
   ↓
窗口接近满 / 用户说结束
   ↓
用户贴 OFFBOARDING 口令
   ↓
Claude 跑 checklist 9 步
   ↓
STATUS.md / ONBOARDING.md / 记忆系统都更新
   ↓
下次开新窗口 → 贴 ONBOARDING 口令 → 无缝接上
```

---

## 🗺️ 配套体检 skill（v0.3.2 起）

- **每次 offboard 自动跑 `graphify --update`** —— 增量更新（30-60 秒），保证图谱永远跟代码同步
- **`/proj-graphify`** — 只在**重建图谱**（强制全量）时手动跑：发 MAJOR 版本前 / 大重构后 / 觉得图谱跟代码偏差太大想重置
- **下次 `/diting-onboard` 会自动读** `graphify-out/GRAPH_REPORT.md`（<30 天的会被当项目地图用）
- 跑完后，下次 `/diting-onboard` 会**自动读** `graphify-out/GRAPH_REPORT.md`（<30 天的会被当项目地图用）
