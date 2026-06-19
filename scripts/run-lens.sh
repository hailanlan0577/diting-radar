#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/diting-radar"
PYBIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3

# 飞书 lark-cli（及其依赖 node）在 homebrew；launchd 非登录 shell 的默认 PATH 不含
# /opt/homebrew/bin → 找不到 lark-cli → 飞书静默发不出。补上（Mac Studio 定制版同样处理）。
export PATH="/opt/homebrew/bin:$PATH"

# DeepSeek key: prefer local env file (chmod 600), fall back to macstudio openclaw via ssh
if [ -f "$HOME/.diting.env" ]; then
  set -a; source "$HOME/.diting.env"; set +a
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  DEEPSEEK_API_KEY="$(ssh -o ConnectTimeout=20 macstudio 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(chr(126)+\"/.openclaw/openclaw.json\")))[\"models\"][\"providers\"][\"deepseek\"][\"apiKey\"])"' 2>/dev/null || true)"
  export DEEPSEEK_API_KEY
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  echo "[run-lens] WARN: DEEPSEEK_API_KEY 为空（~/.diting.env 没有且 ssh macstudio 取 key 失败），本次大概率会失败" >&2
fi

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

[ -x "$PYBIN" ] || { echo "[run-lens] ERROR: $PYBIN 不存在或不可执行" >&2; exit 1; }

mkdir -p "$HOME/diting-radar/state"
exec "$PYBIN" -m diting run --lens "$1" >> "$HOME/diting-radar/state/cron-$1.log" 2>&1
