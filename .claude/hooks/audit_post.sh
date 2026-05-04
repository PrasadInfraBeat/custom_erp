#!/usr/bin/env bash
# .claude/hooks/audit_post.sh
# Phase 2 stub: append a JSON line per post-tool invocation.

set -e
LOG_DIR="$(dirname "$0")/../audit_log"
mkdir -p "$LOG_DIR"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TOOL="${CLAUDE_TOOL_NAME:-unknown}"
RESULT="${CLAUDE_TOOL_RESULT_STATUS:-unknown}"
printf '{"ts":"%s","phase":"post","tool":"%s","status":"%s"}\n' "$TS" "$TOOL" "$RESULT" >> "$LOG_DIR/local.jsonl"
exit 0