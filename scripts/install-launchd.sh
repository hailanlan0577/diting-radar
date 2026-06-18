#!/usr/bin/env bash
# install-launchd.sh — Install and load ai.diting.* LaunchAgents
# Safe to re-run (idempotent): unloads existing agents before reloading.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLIST_DIR="$SCRIPT_DIR/launchd"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"

LENSES=(research loops trends)

echo "==> Copying plists to $LAUNCH_AGENTS_DIR ..."
mkdir -p "$LAUNCH_AGENTS_DIR"
cp "$PLIST_DIR/ai.diting.research.plist" "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.loops.plist"    "$LAUNCH_AGENTS_DIR/"
cp "$PLIST_DIR/ai.diting.trends.plist"   "$LAUNCH_AGENTS_DIR/"

echo "==> Loading agents (unload first to ensure idempotency) ..."
for lens in "${LENSES[@]}"; do
  plist="$LAUNCH_AGENTS_DIR/ai.diting.${lens}.plist"
  # Unload silently — ignore error if not previously loaded
  launchctl unload "$plist" 2>/dev/null || true
  launchctl load -w "$plist" || echo "WARN: load 返回非零 for $plist" >&2
  echo "    Loaded: ai.diting.$lens"
done

echo ""
echo "==> Registered ai.diting agents:"
launchctl list | grep diting || echo "(none found — may need a moment to register)"
