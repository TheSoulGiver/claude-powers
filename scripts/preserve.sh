#!/bin/bash
# 上下文压缩前，将关键信息存入 EverMemOS + Soul Fabric。防止长 session 中途失忆。

ENV_FILE="$HOME/.claude-powers.env"
source "$ENV_FILE" 2>/dev/null

EVERMEMOS_API="http://${CLAUDE_POWERS_EVERMEMOS_HOST:-127.0.0.1}:${CLAUDE_POWERS_EVERMEMOS_PORT:-8001}/api/v1"
SOUL_FABRIC_API="http://${CLAUDE_POWERS_SOUL_HOST:-127.0.0.1}:${CLAUDE_POWERS_SOUL_PORT:-12393}/v1/memory"
MY_USER_ID="${CLAUDE_POWERS_USER_ID:-default-user}"

EVERMEMOS_API_KEY="${CLAUDE_POWERS_EVERMEMOS_API_KEY:-}"
AUTH_HEADER=""
[ -n "$EVERMEMOS_API_KEY" ] && AUTH_HEADER="Authorization: Bearer $EVERMEMOS_API_KEY"

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
SUMMARY=$(echo "$INPUT" | jq -r '.summary // empty')
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')

[ -z "$SUMMARY" ] && exit 0

# 写入去重标记
if [ -n "$SESSION_ID" ]; then
  touch "/tmp/claude_session_${SESSION_ID}_preserved" 2>/dev/null
fi

# 1. EverMemOS
curl --noproxy '*' -s -X POST "${EVERMEMOS_API}/memories" \
  -H "Content-Type: application/json" \
  ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
  -d "$(jq -n \
    --arg mid "compact_$(date +%s)" \
    --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    --arg content "上下文压缩前保存 ($CWD): $SUMMARY" \
    --arg uid "$MY_USER_ID" \
    '{message_id:$mid, create_time:$time, sender:$uid,
      sender_name:"Claude Code", content:$content, role:"assistant",
      group_id:"context-preservation", force_extract:true}')" > /dev/null 2>&1

# 2. Soul Fabric
SOUL_KEY="${CLAUDE_POWERS_SOUL_KEY:-}"
if [ -n "$SOUL_KEY" ]; then
  curl --noproxy '*' -s --max-time 5 -X POST "${SOUL_FABRIC_API}/events" \
    -H "Content-Type: application/json" \
    -H "X-Agent-Key: $SOUL_KEY" \
    -H "X-Agent-Id: $MY_USER_ID" \
    -d "$(jq -n \
      --arg idk "$(uuidgen 2>/dev/null || echo compact_$(date +%s))" \
      --arg content "上下文压缩前保存 ($CWD): $SUMMARY" \
      --arg uid "$MY_USER_ID" \
      '{idempotency_key:$idk, user_id:$uid, content_raw:$content,
        source:"claude-code", memory_type:"episode", salience:0.6,
        agent_id:$uid}')" > /dev/null 2>&1
fi

echo "<preserved>"
echo "关键上下文已保存到 EverMemOS + Soul Fabric。如需回忆，使用 memory_search 工具。"
echo "</preserved>"
