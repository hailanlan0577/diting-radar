#!/usr/bin/env bash
# install-launchd.sh — Install and load ai.diting.* LaunchAgents
# Safe to re-run (idempotent): unloads existing agents before reloading.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_DIR="$SCRIPT_DIR/launchd"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

LENSES=(research loops trends dig project)

echo "==> Copying plists to $LAUNCH_AGENTS_DIR ..."
mkdir -p "$LAUNCH_AGENTS_DIR"
cp "$PLIST_DIR/ai.diting.research.plist" "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.loops.plist"    "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.trends.plist"   "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.dig.plist"      "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.project.plist"  "$LAUNCH_AGENTS_DIR/"

echo "==> Loading agents (unload first to ensure idempotency) ..."
for lens in "${LENSES[@]}"; do
  plist="$LAUNCH_AGENTS_DIR/ai.diting.${lens}.plist"
  # Unload silently — ignore error if not previously loaded
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist" || echo "WARN: load 返回非零 for $plist" >&2
  echo "    Loaded: ai.diting.$lens"
done

# Prefetch agent（非 lens）：每天镜头跑之前把 iCloud vault 影子拉回本地，防 research 卡死
echo "==> Installing prefetch agent ..."
cp "$PLIST_DIR/ai.diting.prefetch.plist" "$LAUNCH_AGENTS_DIR/"
launchctl unload "$LAUNCH_AGENTS_DIR/ai.diting.prefetch.plist" 2>/dev/null || true
launchctl load -w "$LAUNCH_AGENTS_DIR/ai.diting.prefetch.plist" || echo "WARN: prefetch load 返回非零" >&2
echo "    Loaded: ai.diting.prefetch"

echo ""
echo "==> Registered ai.diting agents:"
launchctl list | grep diting || echo "(none found — may need a moment to register)"
