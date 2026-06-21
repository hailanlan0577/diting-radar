# 🆘 新 Claude 会话开场 — 60 秒进入状态

> **你是新 Claude，用户刚让你读这份文件。读完后用中文汇报你理解的项目状态，然后问用户下一步要做什么。**
>
> 用户是非程序员，请用生活化中文解释技术细节，不要甩英文术语给他。

## 💡 触发方式（给用户看）

1. **最快** —— 打 `/diting-onboard` 斜杠命令
2. **随口说** —— "继续谛听" / "接手谛听"，Claude 会识别关键词自动触发
3. **完整口令** —— 复制下面这段：
   ```
   继续之前的 谛听 项目。
   请先读 /Users/<dev-user>/diting-radar/ONBOARDING.md
   读完用中文汇报当前状态，然后问我下一步。
   ```

---

## 📍 地形（30 秒必读）

| 维度 | 答案 |
|------|------|
| **源码主分支（开发）** | MacBook `/Users/<dev-user>/diting-radar`（main 分支，framework python） |
| **运行机（部署）** | **Mac Studio（<run-user>，24h 开机）** `/Users/<run-user>/diting-radar`（venv），SSH `macstudio`，launchd 四时段 |
| **远程备份** | `https://github.com/hailanlan0577/diting-radar`（private） |
| **用户操作系统** | macOS Darwin 25；开发机 MacBook Pro M1 Max 64GB，运行机 Mac Studio |

### 🚫 N 大禁忌（已踩过的坑，绝不能再犯）

1. **不要用裸 `python`** —— 本机 `python` 被 alias 到系统 framework python，**不是 venv**。跑测试/装包一律用全路径 `/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest` 或 `python -m pip`（`source .venv/bin/activate` 盖不住 alias）。（2026-06-18）
2. **飞书发消息必须 `--as bot`** —— 用户身份发给自己 open_id 会进飞书"自聊"（看不到）；机器人（皇后的小跟班）私聊才弹出。且需令牌带 `im:message.send_as_user`+`im:message` scope（管理员审核应用后重登 lark-cli）。（2026-06-18）
3. **trends 镜头依赖 `state/interest_profile.yaml` 的 `repos:`** —— 不种 repo 它就空转。爬源都"降级返 []"，所以坏 repo 不报错只是没结果。（2026-06-18）
4. **scrapling 两个坑**（2026-06-18 阶段一）：(a) `StealthyFetcher`(反爬隐身) 本机 import 即报错(browserforge: No headers can be generated)，故 `sources/fetch.py` 把它和 `Fetcher`(HTTP) **分开 import**，反爬域(知乎/CSDN)抓不到就跳过；(b) scrapling 的 `setup_logger()`(@lru_cache) 在 import 时把 `scrapling` logger 设回 INFO 刷 stderr，因 fetch.py 是函数内 lazy import，**必须在每处 scrapling import 之后调 `_quiet_scrapling()` 压回 ERROR** 才不污染 cron 日志。另：`Fetcher.get` 的 timeout 单位是**秒**不是毫秒。
5. **dig 镜头选题**（2026-06-18 阶段二）：往 `state/dig_queue.yaml` 写 `- "话题"` 优先深挖；空了从兴趣自动选；已挖记进 `state/dug_topics.json` 去重；无题当天跳过。dig 走**独立 `run_dig`**（不复用 run_report），投递成功才 `mark_dug`。
6. **Mac Studio 运行环境两坑**（2026-06-18 迁移）：(a) scrapling 必须装 **`scrapling[fetchers]` 全家桶**（playwright/patchright/browserforge/curl_cffi/msgspec 等），裸装 scrapling 则 `import Fetcher` 即 ModuleNotFoundError、搜索抓取静默失效（已写进 pyproject）；隐身 StealthyFetcher 还需 `scrapling install` 浏览器二进制（已装，知乎/CSDN 能抓）。(b) 直连 DuckDuckGo 被墙，**搜索抓取必须走 mihomo 代理** `DITING_FETCH_PROXY=http://127.0.0.1:7890`（run-lens.sh 已设；DeepSeek/飞书不读此变量）。**`无新题/空，跳过`这句歧义**：既可能真没题，也可能搜索抓不到来源（空报告）——排查 dig 先确认搜索通不通。
7. **launchd 跑的脚本必须自己补 PATH**（2026-06-19）—— launchd 用 `/bin/bash`（非登录 shell），默认 PATH 只有 `/usr/bin:/bin:/usr/sbin:/sbin`，**不含 `/opt/homebrew/bin`** → 找不到 `lark-cli`(及依赖 node) → 飞书**静默**发不出（旧 feishu.py `except: return False` 吞了错，藏了一整天）。`run-lens.sh` 已加 `export PATH="/opt/homebrew/bin:$PATH"`。⚠️验证无人值守任务别用 `bash -l`（登录 shell PATH 完整会掩盖问题），要用 `launchctl kickstart -k gui/$(id -u)/<label>` 走真实环境或 `env -i PATH=/usr/bin:/bin ...` 模拟精简环境。
8. **iCloud vault 的「影子」(dataless) 文件别慌**（2026-06-19/21）—— 新文件刚同步 / 优化储存 evict 的旧文件是占位符，`os.listdir`/`open` 读到可能永久卡死。已三重防护：`obsidian.py` 守护线程超时(超 10s 跳过该目录) + `ai.diting.prefetch` 定时(每天 4 次拉回影子) + iCloud 自愈。prefetch 偶尔「拉回 0/N」是新文件同步的瞬时态、会自愈，**非 bug**，别去重复排查。

---

## 🎯 项目是什么（10 秒）

**谛听 · 个人技术情报雷达** — 每天读你做过的事（Obsidian 会话记录）→ DeepSeek V4 Pro 蒸出你在追什么 → 爬全网（arXiv/HN/GitHub/searxng）→ **砍掉你已经知道的** → 合成带"为什么对你重要"的情报 → 飞书 + Obsidian 双通道送达。服务用户本人，专治"重复造轮子 / 信息过时 / 卡点没人帮"。

技术栈：Python 3.11（httpx / pyyaml / sqlite3 / trafilatura / pytest），全程 DeepSeek V4 Pro，跑 Mac Studio... 不，跑**本机 launchd**。

---

## 📊 当前状态（截至 2026-06-18）

| Phase | 状态 | 说明 |
|-------|------|------|
| 0 基础设施 | ✅ | 仓库/53 测试绿/GitHub 私有仓/launchd 定时 |
| 1 引擎 + 科研雷达 (v1) | ✅ | 信号→蒸馏→爬→去重→合成→飞书+Obsidian 端到端，真跑验收过 |
| 2 四镜头 + 定时 (v2) | ✅ | loops/trends/**dig** 镜头 + launchd 10/14/18/20 四时段，**已迁 Mac Studio 跑** |
| 3 反馈闭环 + 中文源 + 二奢镜头 (v3) | ⏳ | 未启动 |

### 🔴 当前阻塞 / 主攻目标

**无硬阻塞**——谛听已于 2026-06-18 迁到 Mac Studio（<run-user>，24h 开机）自动跑，4 镜头真跑验收通过。可选打磨项见下方"下一步候选"。

---

## 🚦 下一步候选（用户还没拍板）

| 选项 | 动作 | 代价 | 推荐 |
|------|------|------|------|
| **A** | v3 反馈闭环（点有用/没用 → 自学习调关注清单/阈值） | 中 | |
| **B** | 修打磨项：`来源:?`(synthesize url 模糊匹配) + searxng 走代理 | 小 | ⭐ |
| **C** | 加二奢生意情报镜头（另一台引擎，并入或独立） | 大 | |

**你要做的**：问用户选哪个，不要自己拍板。

---

## 📚 更多信息去哪找

| 文档 | 什么时候读 |
|------|-----------|
| `STATUS.md`（本仓库） | 想知道 Phase 细节、每天做过什么、下次第一件事 |
| `CLAUDE.md`（本仓库） | 想跑/部署/连飞书、了解代码地图 |
| `RUNBOOK.md`（本仓库） | 自动任务没发情报 / 要换 key / 要重建 / 紧急救命 |
| `docs/superpowers/specs/2026-06-18-diting-radar-design.md` | 完整设计（v1+v2 由此而来） |
| `docs/superpowers/plans/2026-06-18-diting-radar-v2.md` | v2 实现计划（v3 可参考其结构） |

---

## 🛠️ 常用操作速查

```bash
# 手动跑一个镜头（在 Mac Studio，research/loops/trends/dig）
ssh macstudio 'bash -l -c "cd ~/diting-radar && bash scripts/run-lens.sh research; tail -20 state/cron-research.log"'

# 确认 launchd 4 定时还在（Mac Studio）
ssh macstudio 'launchctl list | grep diting'

# 全套测试（MacBook 开发机）
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q
```

---

## ⚠️ 上一次会话 Claude 踩的坑

1. **2026-06-18**: 多个子代理报"full suite XX 通过"其实没真跑全（websearch 因 lxml_html_clean 缺失收集失败）。教训：控制器要自己 `python -m pytest -q` 核实真实数，别全信子代理报告。
2. **2026-06-18**: 一开始飞书发不出（自聊不可见）、key 装错解释器（python alias 坑）——见禁忌 1、2。
3. **2026-06-18 迁移**: dig 在 Mac Studio "无新题/空，跳过"折腾半天——根因是 scrapling Fetcher 缺 playwright/browserforge（import 即崩，搜索静默返空）+ DDG 直连被墙要走代理。教训：dig 空时先单独测 `search_engine`/`Fetcher import` 而不是怀疑选题逻辑——见禁忌 6。

---

## 🎬 你现在该做什么

1. 检查 `graphify-out/GRAPH_REPORT.md` 是否存在且 < 30 天（有就读三节塞进汇报；无就提一句可跑 `/proj-graphify`）
2. 扫 Obsidian 最近 `diting` tag 文档（前 3 篇）
3. 用中文总结项目状态（3-5 句）+ 第 1/2 步找到的资料
4. 问用户下一步（A/B/C 或读某文档细节）
5. **等用户回复再动手**

---

## 🛑 会话结束前的职责

感觉上下文接近满了，**主动提醒**："要不要按 OFFBOARDING.md 收尾，让下个窗口无缝接上？" 用户确认后读 `OFFBOARDING.md` 走 9 步。打 `/diting-offboard` 也行。
