#!/bin/bash
# 每次用户发消息时注入当前真实时间
# Claude 没有内置时钟，这个钩子确保 Claude 始终知道真实时间

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
source "$SCRIPT_DIR/../.claude-powers.env" 2>/dev/null

TZ_VAL="${CLAUDE_POWERS_TZ:-Asia/Shanghai}"
echo "$(TZ="$TZ_VAL" date '+%Y-%m-%d %a %H:%M %Z') ($(date -u '+%H:%M UTC'))"
