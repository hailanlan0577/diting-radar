# 谛听 救命手册（RUNBOOK）

> 场景驱动，遇到什么情况查哪里。非程序员友好。
> 关键背景：谛听跑在**本机 launchd**（无远程服务器），每天 10/14/18 点自动跑三镜头。

## 🆘 场景索引

| 我现在... | 去看 |
|-----------|------|
| 开新 Claude 会话想继续 | [§ 1 会话交接](#-1-会话交接) |
| 手动跑一次 / 改完代码"部署" | [§ 2 跑与部署](#-2-跑与部署) |
| 飞书/Obsidian 没收到情报 | [§ 3 没发情报](#-3-没发情报) |
| 换新机器 / 重建 | [§ 4 从零重建](#-4-从零重建) |
| DeepSeek key / 飞书登录失效 | [§ 5 密钥与登录](#-5-密钥与登录) |
| 不确定当前状态 | [§ 6 健康检查](#-6-健康检查) |
| 想暂停/恢复自动任务 | [§ 7 启停定时](#-7-启停定时) |
| 想用 git 日常操作 | [§ 8 Git 速查](#-8-git-速查) |

---

## § 1 会话交接

对 Claude 说"继续谛听"或打 `/diting-onboard`。它会读 `ONBOARDING.md` 汇报状态。
还一头雾水就强制：`项目在 /Users/<dev-user>/diting-radar，先读 ONBOARDING.md / STATUS.md 再说话。`

---

## § 2 跑与部署

谛听没远程服务器，"部署"= 装/重装本机 launchd + 跑测试。

```bash
cd ~/diting-radar
bash scripts/deploy.sh            # 跑测试 + 重装 launchd
bash scripts/deploy.sh --restart  # 只重装 launchd（改了 plist/脚本）
bash scripts/deploy.sh --test     # 只跑测试

# 手动立刻跑一个镜头（research/loops/trends）
bash scripts/run-lens.sh research
```

⚠️ 直接跑 python 要用全路径解释器（`python` 是 alias）：
```bash
export DEEPSEEK_API_KEY=$(grep -o 'DEEPSEEK_API_KEY=.*' ~/.diting.env | cut -d= -f2-)
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m diting run --lens research
```

---

## § 3 没发情报

**情景**：到点了飞书/Obsidian 没收到。

### 3.1 看 cron 日志
```bash
tail -30 ~/diting-radar/state/cron-research.log    # 换 loops/trends
tail -20 ~/diting-radar/state/launchd-research.err  # launchd 级错误（脚本启动前的）
```

### 3.2 常见原因排查
- **日志写 `[research] 0 条 — 今天这块没值得看的`** → 正常（precision-first，今天没新东西，空报告不刷飞书）
- **日志写 `⚠️ DeepSeek 暂时不可用`** → key 失效或 DeepSeek API 挂了，见 § 5
- **日志写 `[run-lens] WARN: DEEPSEEK_API_KEY 为空`** → `~/.diting.env` 没了或 ssh 兜底也失败，见 § 5
- **飞书一条没有但 Obsidian 有** → 飞书 scope/登录失效，见 § 5.2；或报告是空报告（空不发飞书）
- **trends 一直"所有关注 repo 都没出新版"** → 正常（没新 release）；或 `state/interest_profile.yaml` 的 `repos:` 是空的

### 3.3 手动复现
```bash
bash ~/diting-radar/scripts/run-lens.sh research
tail ~/diting-radar/state/cron-research.log
```

---

## § 4 从零重建

**情景**：换新 Mac / 系统重装。

```bash
# 1. 装 gh + 克隆
brew install gh && gh auth login --hostname github.com --web
gh repo clone hailanlan0577/diting-radar ~/diting-radar
cd ~/diting-radar

# 2. 装依赖（用全路径 python，含 lxml_html_clean）
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pip install -e ".[dev]" lxml_html_clean

# 3. 恢复 config.yaml（从 config.example.yaml 拷 + 填真实路径/open_id）
cp config.example.yaml config.yaml   # 然后编辑 feishu_target / 路径

# 4. 恢复 ~/.diting.env（DeepSeek key）
KEY=$(ssh macstudio 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(\"~/.openclaw/openclaw.json\")))[\"models\"][\"providers\"][\"deepseek\"][\"apiKey\"])"')
umask 077; printf 'DEEPSEEK_API_KEY=%s\n' "$KEY" > ~/.diting.env; chmod 600 ~/.diting.env

# 5. 飞书登录（见 § 5.2）
# 6. 种关注清单 repos（编辑 state/interest_profile.yaml）
# 7. 装 launchd
bash scripts/install-launchd.sh
```

---

## § 5 密钥与登录

### 5.1 DeepSeek key
- 权威来源：macstudio `~/.openclaw/openclaw.json` 的 `providers.deepseek.apiKey`
- 本机存放：`~/.diting.env`（`DEEPSEEK_API_KEY=sk-...`，chmod 600）
- 重取：
```bash
KEY=$(ssh macstudio 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(\"~/.openclaw/openclaw.json\")))[\"models\"][\"providers\"][\"deepseek\"][\"apiKey\"])"')
umask 077; printf 'DEEPSEEK_API_KEY=%s\n' "$KEY" > ~/.diting.env; chmod 600 ~/.diting.env
```

### 5.2 飞书登录失效（发不出消息）
飞书走 lark-cli + "皇后的小跟班"机器人（app `cli_REDACTED`）。发消息要令牌带 `im:message.send_as_user` + `im:message` scope。
```bash
# 检查当前 scope
lark-cli auth check --scope "im:message.send_as_user im:message"
# 失效 → 重登（会弹浏览器验证链接，授权后等"登录成功"，别 Ctrl+C）
lark-cli auth login --scope "contact:user.basic_profile:readonly im:message.send_as_user im:message"
# 测试自发自收（必须 --as bot）
lark-cli im +messages-send --as bot --user-id ou_REDACTED --text "谛听投递测试"
```
⚠️ 新 scope 需飞书管理员**审核应用权限**通过后，重登才生效。

### GitHub PAT 过期
```bash
gh auth token   # 取活 token；或 gh auth login
```

---

## § 6 健康检查

```bash
cd ~/diting-radar
launchctl list | grep diting                                   # 三任务应都在（research/loops/trends）
/Library/Frameworks/Python.framework/Versions/3.11/bin/python3 -m pytest -q   # 应 53 passed
tail -5 state/cron-research.log state/cron-loops.log state/cron-trends.log     # 最近自动跑结果
lark-cli auth check --scope "im:message" 2>&1 | head -3        # 飞书还能发不
```

---

## § 7 启停定时

```bash
# 暂停全部自动任务
launchctl unload ~/Library/LaunchAgents/ai.diting.research.plist \
                 ~/Library/LaunchAgents/ai.diting.loops.plist \
                 ~/Library/LaunchAgents/ai.diting.trends.plist
# 恢复（重装即可，幂等）
bash ~/diting-radar/scripts/install-launchd.sh
# 改时间：编辑 scripts/launchd/ai.diting.<lens>.plist 的 StartCalendarInterval，再 install
```

---

## § 8 Git 速查

> Git 是代码的"时光机"：`commit` = 拍存档快照，`push` = 传 GitHub 云端。所有命令在 `~/diting-radar` 执行。

```bash
git status                  # 看改了啥还没提交
git log --oneline -10       # 最近做了什么
git add <具体文件>           # 别用 git add .（怕误提 config.yaml）
git commit -m "type: 描述"   # type = feat/fix/docs/chore
git push                    # 推 GitHub
```

**关键规则**：
- ❌ 别用 `git add .` — 容易误加敏感文件（`config.yaml` 已 gitignore，但保险起见）
- ❌ 别 `git reset --hard` / `git push --force` — 除非 100% 确定
- ✅ commit 前 `git status --ignored --short | grep '!!'` 确认 `config.yaml` 在忽略列

### 🚨 不小心把密钥推上 GitHub
1. 立刻去对应控制台 revoke + 换新 key
2. `brew install git-filter-repo && git filter-repo --path config.yaml --invert-paths --force && git push --force`
3. 验证：`git log --all --full-history -- config.yaml` 应啥都没有
