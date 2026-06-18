#!/usr/bin/env bash
set -euo pipefail
cd "$HOME/diting-radar"
PYBIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3

# DeepSeek key: prefer local env file (chmod 600), fall back to macstudio openclaw via ssh
if [ -f "$HOME/.diting.env" ]; then
  set -a; source "$HOME/.diting.env"; set +a
fi

if [ -z "${DEEPSEEK_API_KEY:-}" ]; then
  DEEPSEEK_API_KEY="$(ssh -o ConnectTimeout=20 macstudio 'python3 -c "import json,os;print(json.load(open(os.path.expanduser(chr(126)+\"/.openclaw/openclaw.json\")))[\"models\"][\"providers\"][\"deepseek\"][\"apiKey\"])"' 2>/dev/null || true)"
  export DEEPSEEK_API_KEY
fi

export GITHUB_TOKEN="${GITHUB_TOKEN:-}"

mkdir -p "$HOME/diting-radar/state"
exec "$PYBIN" -m diting run --lens "$1" >> "$HOME/diting-radar/state/cron-$1.log" 2>&1
