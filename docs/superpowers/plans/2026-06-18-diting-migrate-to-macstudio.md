# 谛听 迁移到 Mac Studio — 执行计划（runbook）

> **给接手的 Claude**：这是一份跨机器迁移 runbook，不是 TDD 代码计划。按步骤 A→H 顺序执行，每步带命令 + 验证。**唯一需要用户亲自配合的是步骤 D（飞书 lark-cli 登录）**，其余都能从 MacBook 这台 ssh 到 Mac Studio 远程完成。

**目标**：把谛听从 MacBook Pro（用户 `<dev-user>`）迁到 Mac Studio（用户 `<run-user>`，SSH 别名 `macstudio`）跑。

**为什么迁**：MacBook Pro 会合盖/关机/带出门，launchd 定点任务（10/14/18/20）在机器睡眠/关机时**漏跑**（macOS 顶多下次开机补一次，时效全失）。**Mac Studio 24 小时开机**，是跑定点服务的正确地方。

**当前状态**：阶段一（scrapling 网搜深化）+ 阶段二（dig 深挖镜头）已在 MacBook 全部完成、合并 main、push GitHub。代码是最新的。

---

## 已核实的 Mac Studio 环境事实（2026-06-18 ssh 核实）

| 项 | 状态 | 说明 |
|----|------|------|
| 用户 / home | `<run-user>` / `/Users/<run-user>` | SSH 别名 `macstudio` |
| **会话记录（输入）** | ✅ 可达 | 同一 iCloud，`~/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/会话记录` 已同步过去 |
| **Obsidian vault（输出）** | ✅ 可达 | 同上路径下 `claude/` 整个 vault 都同步了，写情报会同步回 MacBook |
| **DeepSeek key** | ✅ 本地 | `~/.openclaw/openclaw.json` 的 `models.providers.deepseek.apiKey` |
| **Python 3.11** | ✅ 有 | `/opt/homebrew/bin/python3.11`（3.11.15）；另有 `~/.local/bin/python3.11`、`python3.12` |
| **uv** | ✅ 有 | `~/.local/bin/uv`（0.11.8），用它建 venv |
| **git** | ✅ 有 | 2.50.1 |
| **scrapling 经验** | 🎁 有 | `~/scrapling-test/.venv` 已存在 → Mac Studio 上 `StealthyFetcher`（隐身抓取）**大概率可用**（MacBook 的 browserforge 坏了），迁过去反爬站(知乎/CSDN)可能也能抓 |
| **lark-cli（飞书投递）** | ❌ 没装 | 步骤 D 要装 + 登录（需用户配合）|
| **searxng** | ❌ 没有 | 靠 DuckDuckGo 兜底，可先不装 |

---

## ⚠️ 迁移前必读：硬编码路径清单

谛听代码里有 `/Users/<dev-user>` 硬编码，迁到 <run-user> 必须改。**一处不改就会跑错机器的路径**。清单：

| 文件 | 改什么 |
|------|--------|
| `config.yaml`（不入库，要在 Mac Studio 新建/改）| `session_records_dir` / `vault_inbox_dir` / `dig_vault_dir` / `state_dir` 全部 `/Users/<dev-user>` → `/Users/<run-user>` |
| `scripts/run-lens.sh` | `PYBIN` 改成 venv 的 python；**key 取法改成直接读本地 openclaw（去掉 ssh macstudio 那段）** |
| `scripts/launchd/ai.diting.{research,loops,trends,dig}.plist` | `ProgramArguments` 里 `/Users/<dev-user>/diting-radar/scripts/run-lens.sh` → `/Users/<run-user>/...`；`StandardErrorPath` 同理 |

> `run-lens.sh` 里 `cd "$HOME/diting-radar"` 用的是 `$HOME`，在 <run-user> 下自适应，**不用改**；但 `PYBIN`（写死 framework 路径）和取 key 那段必须改。

---

## 步骤 A：部署代码到 Mac Studio

用 rsync 把本地最新代码推过去（避开 private 仓的 GitHub 认证麻烦）。**排除 state 和 .venv**（state 单独在步骤 E 迁，venv 在步骤 B 重建）。

```bash
# 在 MacBook 这台跑：
rsync -av --exclude '.venv' --exclude 'state/cron-*.log' --exclude 'state/launchd-*.err' \
  ~/diting-radar/ macstudio:~/diting-radar/
```

**验证**：

```bash
ssh macstudio 'ls ~/diting-radar/src/diting/dig.py && ls ~/diting-radar/scripts/run-lens.sh && echo OK'
```
Expected: 打印两个文件路径 + OK。

---

## 步骤 B：在 Mac Studio 建 Python 3.11 venv + 装依赖

谛听原来在 MacBook 用 framework python 全局装；迁到 Mac Studio 改用 **uv 建独立 venv**（更干净，不污染 <run-user> 的全局）。

```bash
ssh macstudio 'bash -l -c "
cd ~/diting-radar
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e .
.venv/bin/python -m pip install scrapling || uv pip install --python .venv/bin/python scrapling
"'
```

> `pyproject.toml` 的 dependencies 已含 scrapling/httpx/pyyaml/trafilatura/lxml_html_clean，`-e .` 会一并装。

**验证 + 顺便确认 StealthyFetcher 在 Mac Studio 能不能用（MacBook 上坏的）**：

```bash
ssh macstudio 'bash -l -c "
cd ~/diting-radar
.venv/bin/python -c \"import scrapling, trafilatura, httpx, yaml; print(scrapling.__version__)\"
.venv/bin/python -c \"from scrapling.fetchers import StealthyFetcher; print(\\\"StealthyFetcher import OK — 隐身抓取可用\\\")\" 2>&1 | tail -2
"'
```
Expected: scrapling 版本号 + 看 StealthyFetcher 是否 import 成功（成功的话，迁后反爬站也能抓，记下来更新 config 的 known_antibot_domains 策略）。

---

## 步骤 C：改路径 + 改 key 取法

### C1. 新建 Mac Studio 的 config.yaml（路径全换 <run-user>）

```bash
ssh macstudio 'cat > ~/diting-radar/config.yaml' <<'CFG'
deepseek:
  base_url: "https://api.deepseek.com/v1"
  model: "deepseek-v4-pro"
  api_key_env: "DEEPSEEK_API_KEY"
signal:
  session_records_dir: "/Users/<run-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/会话记录"
  lookback_days: 5
crawl:
  searxng_url: "http://localhost:8080"
  github_token_env: "GITHUB_TOKEN"
  fetch_top_n: 5
  known_antibot_domains: ["zhihu.com", "csdn.net"]
deliver:
  vault_inbox_dir: "/Users/<run-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/Inbox"
  dig_vault_dir: "/Users/<run-user>/Library/Mobile Documents/iCloud~md~obsidian/Documents/claude/谛听深挖"
  feishu_target: "ou_REDACTED"
  dig_max_sources: 12
state_dir: "/Users/<run-user>/diting-radar/state"
CFG
```

### C2. 改 run-lens.sh：PYBIN 用 venv + key 直接读本地 openclaw

把 Mac Studio 上 `~/diting-radar/scripts/run-lens.sh` 改成（核心两处：`PYBIN` 指 venv、key 不再 ssh 而是读本地 openclaw json）：

```bash
ssh macstudio 'cat > ~/diting-radar/scripts/run-lens.sh' <<'SH'
#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/diting-radar"
PYBIN="$HOME/diting-radar/.venv/bin/python"

# DeepSeek key：本机就是 Mac Studio，直接读本地 openclaw（不再 ssh）
if [ -f "$HOME/.diting.env" ]; then
  set -a; source "$HOME/.diting.env"; set +a
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  DEEPSEEK_API_KEY="$("$PYBIN" -c "import json,os;print(json.load(open(os.path.expanduser('~/.openclaw/openclaw.json')))['models']['providers']['deepseek']['apiKey'])" 2>/dev/null || true)"
  export DEEPSEEK_API_KEY
fi
if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "[run-lens] WARN: DEEPSEEK_API_KEY 为空（~/.diting.env 和 openclaw 都没取到）" >&2
fi

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"
[ -x "$PYBIN" ] || { echo "[run-lens] ERROR: $PYBIN 不存在" >&2; exit 1; }
mkdir -p "$HOME/diting-radar/state"
exec "$PYBIN" -m diting run --lens "$1" >> "$HOME/diting-radar/state/cron-$1.log" 2>&1
SH
ssh macstudio 'chmod +x ~/diting-radar/scripts/run-lens.sh'
```

**验证 key 取得到**：

```bash
ssh macstudio 'bash -l -c "cd ~/diting-radar && DEEPSEEK_API_KEY=\$(.venv/bin/python -c \"import json,os;print(json.load(open(os.path.expanduser(chr(126)+\\\"/.openclaw/openclaw.json\\\")))[\\\"models\\\"][\\\"providers\\\"][\\\"deepseek\\\"][\\\"apiKey\\\"])\"); echo key-len=\${#DEEPSEEK_API_KEY}"'
```
Expected: `key-len=` 后面是个非零数字（说明 key 读到了）。

---

## 步骤 D：装 lark-cli + 登录飞书（⚠️ 需用户配合）

谛听靠 `lark-cli --as bot` 发飞书（"皇后的小跟班"机器人私聊）。Mac Studio 没装 lark-cli，要装 + 登录。

**执行时先核实 MacBook 这台 lark-cli 怎么装的**（照同样方式在 Mac Studio 装）：

```bash
# 在 MacBook 查 lark-cli 来源：
which lark-cli; ls -l $(which lark-cli); brew list 2>/dev/null | grep -i lark || npm ls -g 2>/dev/null | grep -i lark
```

然后在 Mac Studio 同款装上（brew/npm 视来源而定），再**让用户登录**：

```bash
# 在 Mac Studio（可能要用户在浏览器授权"皇后的小跟班"应用）：
ssh macstudio 'lark-cli auth login'   # 具体子命令以 lark-cli --help 为准
```

> 这一步可能要用户在飞书后台/浏览器点授权（拿到带 `im:message` + `im:message.send_as_user` scope 的令牌）。登录令牌存在 Mac Studio <run-user> 的 lark-cli 配置里。**这是整个迁移唯一卡用户的点**，提前跟用户约好。

**验证**：用谛听同款命令发一条测试到飞书：

```bash
ssh macstudio 'lark-cli im +messages-send --as bot --user-id ou_REDACTED --text "【谛听·迁移测试】Mac Studio 投递通了"'
```
Expected: 用户飞书收到这条（机器人私聊弹窗）。

---

## 步骤 E：同步 state（保留去重历史，避免重发已发过的）

把 MacBook 的运行时状态搬过去——这样 Mac Studio 接管后不会把"已经发过的情报"再发一遍，也保留"已挖话题"和"关注清单"。只排除日志。

```bash
# 在 MacBook 这台跑：
rsync -av --exclude 'cron-*.log' --exclude 'launchd-*.err' \
  ~/diting-radar/state/ macstudio:~/diting-radar/state/
```

**验证**：

```bash
ssh macstudio 'ls -la ~/diting-radar/state/ | grep -E "pushed.db|dug_topics|interest_profile|versions"'
```
Expected: 看到 `pushed.db`（去重库）、`dug_topics.json`（已挖）、`interest_profile.yaml`（关注清单）、`versions.json`（版本快照）都在。

---

## 步骤 F：在 Mac Studio 装 launchd（4 时段，路径改 <run-user>）

rsync 过去的 plist 里还是 `/Users/<dev-user>` 路径，先 sed 改成 <run-user>，再用 install 脚本装。

```bash
ssh macstudio 'bash -l -c "
cd ~/diting-radar/scripts/launchd
sed -i \"\" \"s|/Users/<dev-user>|/Users/<run-user>|g\" ai.diting.research.plist ai.diting.loops.plist ai.diting.trends.plist ai.diting.dig.plist
echo === 改后确认 ===
grep -h Users ai.diting.dig.plist
cd ~/diting-radar && bash scripts/install-launchd.sh
"'
```

**验证**：

```bash
ssh macstudio 'launchctl list | grep diting'
```
Expected: 列出 4 个 `ai.diting.{research,loops,trends,dig}`。

---

## 步骤 G：停掉 MacBook 这台的 launchd（避免两台重复跑）

**保留 plist 文件不删**（方便回滚），只 unload。

```bash
# 在 MacBook 这台跑：
for l in research loops trends dig; do
  launchctl unload ~/Library/LaunchAgents/ai.diting.$l.plist 2>/dev/null || true
done
launchctl list | grep diting && echo "⚠️ 还有残留" || echo "✅ MacBook 已无 diting 定时（已全停）"
```

---

## 步骤 H：Mac Studio 真跑验收

手动跑一两个镜头，确认端到端通（爬到料 + 发飞书 + 写 Obsidian + 日志干净）。

```bash
# research（轻量，先验证主链路）
ssh macstudio 'bash -l -c "cd ~/diting-radar && bash scripts/run-lens.sh research; echo ---; tail -15 state/cron-research.log"'
```
看：有没有爬到候选、scrapling 噪音是否为 0、`[research] 日期: N 条`。

```bash
# dig（验证深挖镜头 + Obsidian 长资料）——先放个话题
ssh macstudio 'printf -- "- \"RAG 检索增强新做法\"\n" > ~/diting-radar/state/dig_queue.yaml'
ssh macstudio 'bash -l -c "cd ~/diting-radar && bash scripts/run-lens.sh dig; echo ---; tail -15 state/cron-dig.log"'
```
看 Obsidian `谛听深挖/` 出现新长资料（会同步回 MacBook）+ 飞书收到深挖通知。

> 提醒用户去飞书 + MacBook 的 Obsidian 确认收到（iCloud 同步可能有几分钟延迟）。

---

## 回滚方案（万一迁移出问题）

迁移**不删 MacBook 任何东西**（plist 只 unload 不删、代码/state 都在），随时能滚回：

```bash
# 回滚：恢复 MacBook 定时 + 停 Mac Studio
# MacBook：
for l in research loops trends dig; do launchctl load -w ~/Library/LaunchAgents/ai.diting.$l.plist; done
# Mac Studio：
ssh macstudio 'for l in research loops trends dig; do launchctl unload ~/Library/LaunchAgents/ai.diting.$l.plist 2>/dev/null; done'
```

---

## 最终验收 checklist（全绿才算迁移完成）

- [ ] A 代码已在 Mac Studio `~/diting-radar`（dig.py 等都在）
- [ ] B venv 建好，scrapling/trafilatura 等 import 成功（记下 StealthyFetcher 在 Mac Studio 能否用）
- [ ] C config.yaml 路径全是 <run-user>；run-lens.sh key 直接读本地 openclaw 取得到（key-len 非零）
- [ ] D lark-cli 装好、飞书登录成功、测试消息用户收到
- [ ] E state 已同步（pushed.db/dug_topics/interest_profile/versions 都在）
- [ ] F Mac Studio `launchctl list | grep diting` 见 4 任务
- [ ] G MacBook `launchctl list | grep diting` 已空（停了）
- [ ] H 真跑 research + dig 通：飞书收到 + Obsidian 出文件 + 日志无 scrapling 噪音
- [ ] 收尾：更新 `ONBOARDING.md`/`CLAUDE.md` 的"部署目标"从 MacBook 改成 Mac Studio（<run-user>），commit + push；STATUS 记一笔"已迁 Mac Studio"

---

## 迁移后才需要改的文档（H 通过后做）

- `ONBOARDING.md` / `CLAUDE.md`：地理表"本地 MacBook"→"Mac Studio（<run-user>）24h"；部署路径 `/Users/<dev-user>`→`/Users/<run-user>`；key 取法说明更新（本地 openclaw，不再 ssh）
- 本文档配套的"完整流程图与使用手册"（Obsidian `项目/2026-06-18 谛听 完整流程图与使用手册.md`）：第一节"它住在哪"、第十节路径表都要把 <dev-user>/MacBook 改成 <run-user>/Mac Studio
- `STATUS.md`：追加"2026-XX-XX 迁移到 Mac Studio 完成"

> 这些文档改动放在迁移**验证通过后**做，避免迁移失败时文档与现实不符。

