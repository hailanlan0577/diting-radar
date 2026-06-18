#!/usr/bin/env bash
# sync-status-to-studio.sh —— 在【源机器】(如 MacBook)跑，把本机各项目仓库的救命套件
# STATUS/ONBOARDING 推到 Mac Studio 的 ~/project-status/，供谛听 collect_documents 读取。
#
# 设计：
# - 扁平命名 <host>-<project>-<doc>.md（谛听 collect_documents 不递归，须单层目录）
# - cp -p 保留原 mtime → Mac Studio 上 14 天过滤能正确剔除不活跃项目的旧 STATUS
# - 排除 diting-radar 自己（谛听不读自己的状态，防自循环）
# - 多台源机用 host 前缀避免文件名冲突，可共存于同一汇集目录
set -euo pipefail

HOST=$(hostname -s)
case "$HOST" in
  *MacBook*|*macbook*) HOST=macbook ;;
  *[Mm]ini*)           HOST=macmini ;;
  *Studio*|*studio*)   HOST=macstudio ;;
esac
STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT

n=0
for d in "$HOME"/*/; do
  proj=$(basename "$d")
  [ "$proj" = "diting-radar" ] && continue   # 谛听自己不推（防自循环）
  for f in STATUS ONBOARDING; do
    if [ -f "${d}${f}.md" ]; then
      cp -p "${d}${f}.md" "$STAGE/${HOST}-${proj}-${f}.md"
      n=$((n + 1))
    fi
  done
done

ssh macstudio 'mkdir -p ~/project-status'
if [ "$n" -gt 0 ]; then
  rsync -a "$STAGE"/ macstudio:project-status/
fi
echo "[sync-status] $(date '+%Y-%m-%d %H:%M') 推送 $n 个救命手册文档 → Mac Studio:~/project-status/"
