#!/bin/bash
# guard-claude-process.sh — PreToolUse hook
# 防止 Claude Code 在任何情况下杀死自己或其他 Claude 进程

set -euo pipefail

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command // empty')

[ -z "$COMMAND" ] && exit 0

# 1) 直接 kill/pkill/killall claude 相关进程名
if echo "$COMMAND" | grep -qiE '(pkill|killall)\s+.*(claude|anthropic)'; then
  jq -n '{
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: "已阻止：该命令会直接杀死 Claude 进程。请使用更精确的方式终止目标进程。"
    }
  }'
  exit 0
fi

# 2) kill 后跟 $() 子命令
if echo "$COMMAND" | grep -qE 'kill\s.*\$\('; then
  SUBCMD=$(echo "$COMMAND" | grep -oE '\$\([^)]+\)' | head -1)
  if [ -n "$SUBCMD" ]; then
    INNER=${SUBCMD:2:${#SUBCMD}-3}
    PIDS=$(eval "$INNER" 2>/dev/null || true)
    if [ -n "$PIDS" ]; then
      for PID in $PIDS; do
        if [[ "$PID" =~ ^[0-9]+$ ]]; then
          PROC_CMD=$(ps -p "$PID" -o args= 2>/dev/null || true)
          if echo "$PROC_CMD" | grep -qiE '(claude|anthropic)'; then
            jq -n --arg pid "$PID" --arg cmd "$PROC_CMD" '{
              hookSpecificOutput: {
                hookEventName: "PreToolUse",
                permissionDecision: "deny",
                permissionDecisionReason: ("已阻止：命令会杀死 PID " + $pid + " (" + $cmd + ")，这是一个 Claude 进程。")
              }
            }'
            exit 0
          fi
        fi
      done
    fi
  fi
fi

# 3) 直接 kill <PID>
if echo "$COMMAND" | grep -qE '^\s*kill\s'; then
  PIDS=$(echo "$COMMAND" | grep -oE '\b[0-9]{2,}\b' || true)
  for PID in $PIDS; do
    PROC_CMD=$(ps -p "$PID" -o args= 2>/dev/null || true)
    if echo "$PROC_CMD" | grep -qiE '(claude|anthropic)'; then
      jq -n --arg pid "$PID" --arg cmd "$PROC_CMD" '{
        hookSpecificOutput: {
          hookEventName: "PreToolUse",
          permissionDecision: "deny",
          permissionDecisionReason: ("已阻止：PID " + $pid + " (" + $cmd + ") 是 Claude 进程，不能杀死。")
        }
      }'
      exit 0
    fi
  done
fi

# 4) 管道模式：lsof/pgrep | xargs kill
if echo "$COMMAND" | grep -qE '\|\s*(xargs\s+)?kill'; then
  PIPE_PREFIX=$(echo "$COMMAND" | sed 's/|.*//')
  PIDS=$(eval "$PIPE_PREFIX" 2>/dev/null || true)
  if [ -n "$PIDS" ]; then
    for PID in $PIDS; do
      if [[ "$PID" =~ ^[0-9]+$ ]]; then
        PROC_CMD=$(ps -p "$PID" -o args= 2>/dev/null || true)
        if echo "$PROC_CMD" | grep -qiE '(claude|anthropic)'; then
          jq -n --arg pid "$PID" --arg cmd "$PROC_CMD" '{
            hookSpecificOutput: {
              hookEventName: "PreToolUse",
              permissionDecision: "deny",
              permissionDecisionReason: ("已阻止：管道命令会杀死 Claude 进程 PID " + $pid + "。请过滤掉 Claude 进程。")
            }
          }'
          exit 0
        fi
      fi
    done
  fi
fi

# 5) pkill/killall node/npm/npx（可能误杀 Claude Code）
if echo "$COMMAND" | grep -qiE '(pkill|killall)\s+(-\w+\s+)*(node|npm|npx)(\s|$)'; then
  CLAUDE_NODES=$(pgrep -f "claude" 2>/dev/null | head -5 || true)
  if [ -n "$CLAUDE_NODES" ]; then
    jq -n '{
      hookSpecificOutput: {
        hookEventName: "PreToolUse",
        permissionDecision: "deny",
        permissionDecisionReason: "已阻止：pkill/killall node 会杀死当前运行的 Claude Code 进程。请用 lsof -ti :PORT 找到具体 PID。"
      }
    }'
    exit 0
  fi
fi

exit 0
