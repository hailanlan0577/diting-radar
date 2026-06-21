# 项目当前状态

> 最后更新：2026-06-19
> 新 Claude 进门先读 `CLAUDE.md`（地形 + 部署），再读本文件（进度 + 下一步）。

## 🎯 一句话

谛听 v1+v2 全部上线，4 镜头 + launchd 四时段定时**已于 2026-06-18 迁到 Mac Studio（<run-user>，24h 开机）自动跑**；MacBook 定时已停。飞书+Obsidian 双通道实测送达。**无硬阻塞**，下一步是 v3 打磨/增强。

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

## 📝 2026-06-21 做了什么

### 2026-06-21（✅ 验证飞书修复在真实定时下生效 + prefetch 加固）

- **验证 launchd 飞书修复**：dig 06-19 自然挖《iCloud 优化存储导致进程卡死在 os.listdir》、06-20 挖《谛听项目维护与问题排查》，`dug_topics.json` 都登记了——因代码是"投递成功才 mark_dug"，**能登记 = 飞书发成功的铁证**。loops 06-20 也出 6 条。launchd PATH 修复确认在真实定时下生效。
- **排查 prefetch「拉回 0/N」= 非 bug**：那些影子是新文件刚从别的设备同步到 Mac Studio 的瞬时态（iCloud 先放 dataless 占位、内容过几秒才传完），prefetch 撞上传输中间态当下抓失败，iCloud 随后自愈（次日全"无影子"为证）。诊断关键：14:47 的会话记录在 13:50 prefetch 跑时还没创建 → 13:50 拉回 0 的是另外早已自愈的文件。系统三重容错（守护线程超时 + prefetch 4 次/天 + iCloud 自愈），不影响推送。
- **✅ prefetch 加固**（commit bb593e0）：`prefetch-vault.py` 下载改以"是否仍 dataless"为成功判据，失败隔 5s 重试 2 次（应对瞬时态），日志记录拉不回的文件名+原因（原仅记数量）。环境变量 `DITING_PREFETCH_RETRIES`/`BACKOFF` 可调。evict 旧文件端到端测试：拉回 1/1。

---

## 📝 2026-06-19 做了什么

### 2026-06-19（🩹 修 iCloud 卡死导致 research 僵死无推送 ✅）

**现象**：早上 10:00 research 没推送。排查发现 launchd 起的 research 进程从 10:00 卡死——CPU 时间死在 0.3 秒不增长、无任何网络连接、STAT=S；`sample <pid> 4` 抓栈 4 秒采样 100% 卡在 `os_listdir → __opendir2 → open$NOCANCEL`。

**根因**：信号源收集 `os.listdir` 读 Obsidian 的 iCloud 目录（`~/Library/Mobile Documents/iCloud~md~obsidian/...`）时，Mac Studio 的 iCloud 文件提供者（fileproviderd）偶发抽风/按需下载卡死，`opendir()` 永久阻塞内核态 → 整个谛听僵在第一步"读笔记"，走不到爬取/合成/投递 → 无推送。全项目 listdir 只有 `obsidian.py:21` 一处。昨天能跑今天卡 = iCloud 间歇性问题。反证：杀掉卡死进程后，同代码同 8 个目录 3 分钟跑通出 4 条；逐目录复测全 0.0x 秒秒回（旧进程的 open 已永久挂死，目录后来恢复也醒不过来）。

**修复**：`obsidian.py` 的 `_collect_md_dir` 加守护线程超时保护——拆出 `_read_md_dir`（实际 listdir+读文件），外层用 `threading.Thread(daemon=True)+join(_LISTDIR_TIMEOUT)` 包裹，超时（默认 10s，`DITING_DIR_TIMEOUT` 可调）未读完就跳过该目录返回 `[]`，绝不拖垮整个进程；`daemon=True` 保证卡住线程不阻塞进程退出（不能用 ThreadPoolExecutor，其非 daemon 线程会在解释器退出时被 atexit join 而卡住）。去掉原 `os.path.isdir` 检查，改由 `os.listdir` 抛 OSError 兜底。新增 `test_collect_md_dir_skips_hanging_dir`（97 测试全绿）。

**止血 + 部署**：`kill -9` 卡死进程 + 手动 `run-lens.sh research` 补当天 4 条情报；⚠️只 `rsync obsidian.py` 单文件到 Mac Studio（不整目录 rsync，避免覆盖定制的 run-lens.sh），真实 iCloud 目录验证读 11 会话+12 文档 0.0x 秒秒回。

**iCloud 双层根治（运维）**：① 强制下载——`scripts/prefetch-vault.py` 扫 vault 找影子(dataless)文件拉回本地，实测清掉 317 个、0 残留；② 防复发——新增 `ai.diting.prefetch` launchd 定时（每天 9:50/13:50/17:50/19:50 赶在四镜头前自动拉回影子），已并入 `install-launchd.sh`。现 Mac Studio 共 **5 个 launchd**（4 镜头 + prefetch）。「优化 Mac 储存空间」开关用户选择保留开启（关掉其实不省空间——那 554G 是照片+备份、开关只管云盘的 391M；但有 prefetch + 代码超时双保险，开不开都行）。

### 2026-06-19（🐛 修 launchd 缺 PATH 导致飞书静默发不出 ✅）

**现象**：下午 loops(14:00) 跑出 2 条、trends(18:00) 0 条，飞书都没收到（trends 0 条本就不发=正常；loops 2 条该发没发=bug）。Obsidian 写进去了，飞书没有。

**根因**：launchd 用 `/bin/bash`（非登录 shell）跑 run-lens.sh，默认 PATH(`/usr/bin:/bin:...`) 不含 `/opt/homebrew/bin` → 找不到 `lark-cli`（及其依赖 node）→ `feishu.py` 的 subprocess 抛 FileNotFoundError → 被 `except: return False` **静默吞掉** → 飞书发不出且日志无错误。早上 research 是我手动用登录 shell(`bash -l`)补跑的(PATH 完整)反而掩盖了它——今天 loops/trends 是 launchd 第一次真正走到飞书投递才暴露。

**修复**：① `run-lens.sh` 开头加 `export PATH="/opt/homebrew/bin:$PATH"`（Mac Studio 定制版已改 + 本地 git 版同步）；② `feishu.py` 提取 `_run_lark`，发送失败/异常时打印 `[feishu] ...` 到 stderr（进 cron 日志），不再静默——这是 bug 藏一天的元凶。新增 2 测试（99 绿）。验证：kickstart loops 走真 launchd 环境 + 精简环境真发飞书 `returncode=0`/`ok:true`，通道恢复。

---

## 📝 2026-06-18 做了什么

### 2026-06-18（🔭 信号源扩展 A+C ✅）

把"了解你"的信号源从**只读会话记录**扩展到**会话记录 + 6 个高价值项目目录的近期文档**（二奢软件/项目/复盘/故障复盘/Mac Studio AI 底座/工具）：
- `obsidian.py` 加 `collect_documents`（每篇截断 1500 字 + 带文件名，按 mtime 取最新 12 篇，排除"谛听情报/谛听深挖"自产出防自循环）；重构出共享 `_collect_md_dir`。
- `config.py` 加 `signal.extra_doc_dirs` + `extra_lookback_days`（默认 14 天）；`distill` 预算 24000→40000 容纳两类信号；runner/dig 合并两类信号。
- 5 个新测试（96 绿）。实测 Mac Studio 读到 14 会话 + 12 项目文档（ytst M3/二奢买手薪酬/谛听手册 等真实项目），research 真跑 8 条（扩展前 3 条）。commit 6ae6cde。
- 📡 **跨机器 STATUS 同步**（commit 7f0b730）：`scripts/sync-status-to-studio.sh` 在 **MacBook** 跑（launchd `ai.diting.statussync`：登录即推 + 开着时每 6h 推一次，不挑固定时间避开睡觉时段，谛听第二天读即可），把各项目仓库 STATUS/ONBOARDING 扁平命名（`macbook-<proj>-`）推到 Mac Studio `~/project-status/`（已加进 extra_doc_dirs）。**方向 MacBook→Studio 单推**（Studio 够不着 MacBook）。实测推 18 文档，谛听经 14 天过滤读到 ytst/survival-kit-pro 等活跃项目 STATUS。Mac Mini 暂未接（没配 macstudio 别名 + 其项目已不活跃）。

### 2026-06-18（🚚 迁移到 Mac Studio 完成 ✅）

1. ✅ **8 步 A-H 全过**：rsync 代码 → uv 建 venv 装依赖 → config/run-lens 路径换 <run-user> + key 改读本地 openclaw → lark-cli 配飞书 → 同步 state 去重历史 → 装 4 launchd → 停 MacBook launchd → research(3条)+dig(12篇) 真跑验收。
2. 🐛 **坑1：scrapling 0.4.9 的 Fetcher(HTTP) 有隐藏依赖链** —— `from scrapling.fetchers import Fetcher` 缺 playwright→browserforge→curl_cffi 任一即 ModuleNotFoundError，搜索/抓正文静默失效（被 except 兜底返空：research 靠 arxiv/hn/github API 兜底没暴露，dig 全靠搜索就垮）。修：venv 补装这三个 + 写进 `pyproject.toml` dependencies 固化。
3. 🐛 **坑2：Mac Studio 直连 DuckDuckGo 被墙** —— 必须走 mihomo 代理 `127.0.0.1:7890`。修：`fetch.py` 加 `_proxy()` 读环境变量 `DITING_FETCH_PROXY`，Mac Studio 的 run-lens.sh 设上（DeepSeek 国内直连/飞书走 lark-cli 都不读这变量，互不影响）。MacBook 不设=直连，原行为不变。
4. ✅ **飞书配置免浏览器授权**：lark-cli 钥匙串存的是加密主钥（master.key）非明文密钥，导不出；改用 `config init --app-id cli_REDACTED --app-secret-stdin`（用户从开放平台复制 App Secret），机器人身份纯靠密钥换租户令牌，**没用上 device flow 浏览器授权**。
5. ✅ **隐身抓取 StealthyFetcher 已启用**（2026-06-18 晚补 `scrapling[fetchers]` 全依赖含 patchright/msgspec + `scrapling install` 浏览器二进制；实测隐身抓 CSDN 拿到 424 字正文）→ 反爬域(知乎/CSDN)现在能抓正文，不再跳过。比 MacBook 还强（MacBook 的 browserforge 坏着）。

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

**✅ 2026-06-18/19 大改全部完成 + 验收**：迁 Mac Studio(4 镜头 24h) + 隐身抓取启用 + 信号源扩展(会话记录 + 6 个 vault 目录 + 各项目仓库 STATUS 跨机器同步)。MacBook 仅留 statussync 推送定时。

**✅ 2026-06-19 修了 iCloud 卡死 bug**：research 因 iCloud 抽风卡在 `os.listdir` 僵死、整天无推送 → 给信号目录读取加守护线程超时保护（超 10s 跳过该目录），已部署 Mac Studio。详见上方「2026-06-19 做了什么」。观察点：之后若某天某镜头偶尔少几条，可能是某目录被超时跳过（看 cron log），属预期容错、非故障。

**✅ 2026-06-21 飞书修复验证 + prefetch 加固**：dig 06-19/06-20 在真实 launchd 定时下飞书推送成功（dug_topics 登记=铁证）；prefetch 偶发"拉回 0/N"查明为 iCloud 新文件同步瞬时态、会自愈、**非 bug**，并加了失败重试 + 失败文件名日志。

**下次第一件事**：**没有待办，系统健康运行中**（5 个定时全绿 = 4 镜头 + prefetch、飞书通道通、iCloud 三重容错）。想推进就挑一个可选打磨项：① 修 `来源:?`(synthesize url 模糊匹配) ② searxng 走代理 ③ v3 反馈闭环(点有用/没用自学习) ④ 二奢生意情报镜头。或等用户提新需求。

> ⚠️ **改谛听代码的流程变了**：MacBook `/Users/<dev-user>/diting-radar` 仍是开发+测试+commit/push 的主分支 → 改完 `rsync src/ scripts/ 到 macstudio` → 如改了 plist 再 `ssh macstudio` 重装 launchd。详见 CLAUDE.md「部署工作流」。
> 回滚：MacBook `for l in research loops trends dig; do launchctl load -w ~/Library/LaunchAgents/ai.diting.$l.plist; done` + Mac Studio 对应 unload。

---

阶段一/二已上线（scrapling 网搜深化 + dig 深挖镜头，91 测试，合并 main）。迁移后可选打磨：dig 加 gh 扒代码仓(v2) / searxng 代理 / 修隐身抓取(Mac Studio 上 browserforge 可能本就好的)。
