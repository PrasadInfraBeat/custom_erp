#!/usr/bin/env bash
# .claude/hooks/audit_pre.sh
# Phase 2 stub: append a JSON line per pre-tool invocation.
# Real audit pipeline lands in InfraBeat Console (later phase).

set -e
LOG_DIR="$(dirname "$0")/../audit_log"
mkdir -p "$LOG_DIR"
TS=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
TOOL="${CLAUDE_TOOL_NAME:-unknown}"
printf '{"ts":"%s","phase":"pre","tool":"%s"}\n' "$TS" "$TOOL" >> "$LOG_DIR/local.jsonl"
exit 0