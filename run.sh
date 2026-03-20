#!/usr/bin/env bash
# daily-info-push 定时任务包装脚本
# 用法: ./run.sh [morning|evening]

set -euo pipefail

# 切换到脚本所在目录（项目根目录），确保 uv 能找到 pyproject.toml
cd "$(dirname "$(readlink -f "$0")")"

EDITION="${1:-}"
DATE="$(date +%F)"
LOG_DIR="${HOME}/.daily-info-push/logs"
mkdir -p "$LOG_DIR"
LOG_FILE="${LOG_DIR}/${DATE}_${EDITION:-default}.log"

echo "===== $(date '+%Y-%m-%d %H:%M:%S') run start (edition=${EDITION:-none}) =====" >> "$LOG_FILE"

uv run python main.py --date "$DATE" ${EDITION:+--edition "$EDITION"} >> "$LOG_FILE" 2>&1

echo "===== $(date '+%Y-%m-%d %H:%M:%S') run end =====" >> "$LOG_FILE"
