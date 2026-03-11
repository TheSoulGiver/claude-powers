#!/bin/bash
# 入眠 Hook — 用 LLM 提取 session 摘要，写到 EverMemOS + Soul Fabric + 日记

ENV_FILE="$HOME/.claude-powers.env"
source "$ENV_FILE" 2>/dev/null

EVERMEMOS_API="http://${CLAUDE_POWERS_EVERMEMOS_HOST:-127.0.0.1}:${CLAUDE_POWERS_EVERMEMOS_PORT:-8001}/api/v1"
SOUL_FABRIC_API="http://${CLAUDE_POWERS_SOUL_HOST:-127.0.0.1}:${CLAUDE_POWERS_SOUL_PORT:-12393}/v1/memory"
MY_USER_ID="${CLAUDE_POWERS_USER_ID:-default-user}"

EVERMEMOS_API_KEY="${CLAUDE_POWERS_EVERMEMOS_API_KEY:-}"
AUTH_HEADER=""
[ -n "$EVERMEMOS_API_KEY" ] && AUTH_HEADER="Authorization: Bearer $EVERMEMOS_API_KEY"

INPUT=$(cat)
SESSION_ID=$(echo "$INPUT" | jq -r '.session_id // empty')
TRANSCRIPT=$(echo "$INPUT" | jq -r '.transcript_path // empty')
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')

[ -z "$TRANSCRIPT" ] || [ ! -f "$TRANSCRIPT" ] && exit 0

# 提取结构化信息
FILES=$(jq -r 'select(.type=="tool_use" and (.name=="Write" or .name=="Edit")) |
  .input.file_path // empty' "$TRANSCRIPT" 2>/dev/null | sort -u | head -20)
COMMITS=$(jq -r 'select(.type=="tool_use" and .name=="Bash") |
  .input.command // empty' "$TRANSCRIPT" 2>/dev/null | grep "git commit" | head -5)
USER_MSGS=$(jq -r 'select(.type=="human") | .content // empty' "$TRANSCRIPT" 2>/dev/null | head -c 2000)
ASSISTANT_MSGS=$(jq -r 'select(.type=="assistant") | .content // empty' "$TRANSCRIPT" 2>/dev/null | tail -c 2000)

[ -z "$FILES" ] && [ -z "$USER_MSGS" ] && exit 0

# 去重：检查 preserve hook 是否已写过本 session 的记忆
DEDUP_MARKER="/tmp/claude_session_${SESSION_ID}_preserved"
if [ -f "$DEDUP_MARKER" ]; then
  SKIP_REMOTE=1
else
  SKIP_REMOTE=0
fi

# === LLM 摘要 ===
ANTHROPIC_KEY="${CLAUDE_POWERS_ANTHROPIC_KEY:-}"
ANTHROPIC_URL="${CLAUDE_POWERS_ANTHROPIC_URL:-https://api.anthropic.com}"

CONTEXT="目录: $CWD
${FILES:+修改的文件:\n$FILES\n}
${COMMITS:+Git提交:\n$COMMITS\n}
用户说了什么:
$USER_MSGS

助手最后的回复:
$ASSISTANT_MSGS"

LLM_SUMMARY=""
if [ -n "$ANTHROPIC_KEY" ]; then
  LLM_SUMMARY=$(curl --noproxy '*' -s --max-time 8 -X POST "${ANTHROPIC_URL}/v1/messages" \
    -H "Content-Type: application/json" \
    -H "x-api-key: $ANTHROPIC_KEY" \
    -H "anthropic-version: 2023-06-01" \
    -d "$(jq -n \
      --arg ctx "$CONTEXT" \
      '{model:"claude-haiku-4-5-20251001", max_tokens:300,
        messages:[{role:"user",content:("从这个编码session中提取关键信息，用中文，格式:\n- 做了什么（1-2句）\n- 关键决策或发现（如有）\n- 遗留问题（如有）\n不超过150字。\n\n" + $ctx)}]}')" 2>/dev/null | \
    jq -r '.content[0].text // empty' 2>/dev/null)
fi

# 构建最终摘要
TIMESTAMP=$(date '+%Y-%m-%d %H:%M')
if [ -n "$LLM_SUMMARY" ]; then
  SUMMARY="[$TIMESTAMP] $CWD
$LLM_SUMMARY
${FILES:+\n文件: $(echo "$FILES" | tr '\n' ', ')}"
  SALIENCE="0.8"
else
  if [ -n "$FILES" ]; then
    SUMMARY="编码经历 ($TIMESTAMP)
目录: $CWD
${FILES:+修改的文件:\n$FILES}
${COMMITS:+提交:\n$COMMITS}"
    SALIENCE="0.7"
  else
    SUMMARY="对话记录 ($TIMESTAMP)
目录: $CWD
用户话题: $(echo "$USER_MSGS" | head -c 500)"
    SALIENCE="0.4"
  fi
fi

# 1. 存入 EverMemOS（如果 preserve 没写过）
if [ "$SKIP_REMOTE" -eq 0 ]; then
  curl --noproxy '*' -s -X POST "${EVERMEMOS_API}/memories" \
    -H "Content-Type: application/json" \
    ${AUTH_HEADER:+-H "$AUTH_HEADER"} \
    -d "$(jq -n \
      --arg mid "cc_${SESSION_ID}_$(date +%s)" \
      --arg time "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      --arg content "$SUMMARY" \
      --arg uid "$MY_USER_ID" \
      '{message_id:$mid, create_time:$time, sender:$uid,
        sender_name:"Claude Code", content:$content, role:"assistant",
        group_id:"coding-experience", force_extract:true}')" > /dev/null 2>&1

  # 2. 双写 Soul Memory Fabric
  SOUL_KEY="${CLAUDE_POWERS_SOUL_KEY:-}"
  if [ -n "$SOUL_KEY" ]; then
    curl --noproxy '*' -s --max-time 5 -X POST "${SOUL_FABRIC_API}/events" \
      -H "Content-Type: application/json" \
      -H "X-Agent-Key: $SOUL_KEY" \
      -H "X-Agent-Id: $MY_USER_ID" \
      -d "$(jq -n \
        --arg idk "$(uuidgen 2>/dev/null || echo cc_${SESSION_ID}_$(date +%s))" \
        --arg uid "$MY_USER_ID" \
        --arg content "$SUMMARY" \
        --arg sal "$SALIENCE" \
        '{idempotency_key:$idk, user_id:$uid, content_raw:$content,
          source:"claude-code", memory_type:"episode", salience:($sal|tonumber),
          agent_id:$uid}')" > /dev/null 2>&1
  fi
fi

# 3. 日记文件
mkdir -p "$HOME/.claude-powers/diary" 2>/dev/null
echo -e "\n### Claude Code $(date '+%H:%M')\n$SUMMARY" \
  >> "$HOME/.claude-powers/diary/$(date +%Y-%m-%d).md" 2>/dev/null

exit 0
