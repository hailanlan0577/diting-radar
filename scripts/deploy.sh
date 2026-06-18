#!/usr/bin/env bash
# 谛听本机"部署"：跑测试 + 装/重装 launchd 定时（无远程服务器）
# 用法：
#   bash scripts/deploy.sh            # 跑测试 + 重装 launchd
#   bash scripts/deploy.sh --restart  # 只重装 launchd（改了 plist/脚本）
#   bash scripts/deploy.sh --test     # 只跑测试
#   bash scripts/deploy.sh --run <lens>   # 立刻手动跑一个镜头（research/loops/trends/dig）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"
PYBIN=/Library/Frameworks/Python.framework/Versions/3.11/bin/python3

log()  { printf "\033[1;36m[deploy]\033[0m %s\n" "$*"; }
ok()   { printf "\033[1;32m✅\033[0m %s\n" "$*"; }
fail() { printf "\033[1;31m❌\033[0m %s\n" "$*" >&2; exit 1; }

MODE="${1:-full}"

case "$MODE" in
  --test)
    log "跑全套测试..."
    "$PYBIN" -m pytest -q || fail "测试没过，先修测试再部署"
    ok "测试通过"
    ;;
  --restart)
    log "重装 launchd 定时..."
    bash "$REPO_ROOT/scripts/install-launchd.sh"
    ok "launchd 已重装"
    ;;
  --run)
    LENS="${2:-research}"
    log "手动跑 $LENS 镜头..."
    bash "$REPO_ROOT/scripts/run-lens.sh" "$LENS"
    ok "跑完，看 state/cron-$LENS.log"
    tail -4 "$REPO_ROOT/state/cron-$LENS.log" 2>/dev/null || true
    ;;
  full|"")
    log "① 跑全套测试..."
    "$PYBIN" -m pytest -q || fail "测试没过，先修测试再部署"
    ok "测试通过"
    log "② 装/重装 launchd 定时..."
    bash "$REPO_ROOT/scripts/install-launchd.sh"
    ok "部署完成：测试绿 + launchd 四时段已就位"
    log "确认：launchctl list | grep diting"
    ;;
  *)
    fail "未知模式：$MODE（用 --test / --restart / --run <lens> 或不带参数）"
    ;;
esac
