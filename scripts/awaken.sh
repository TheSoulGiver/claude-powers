#!/bin/bash
# 唤醒 Hook — 读取 EverMemOS + Soul Memory Fabric 记忆，注入 Claude Code 上下文

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="$HOME/.claude-powers.env"
source "$ENV_FILE" 2>/dev/null

EVERMEMOS_API="http://${CLAUDE_POWERS_EVERMEMOS_HOST:-127.0.0.1}:${CLAUDE_POWERS_EVERMEMOS_PORT:-8001}/api/v1"
SOUL_FABRIC_API="http://${CLAUDE_POWERS_SOUL_HOST:-127.0.0.1}:${CLAUDE_POWERS_SOUL_PORT:-12393}/v1/memory"
MY_USER_ID="${CLAUDE_POWERS_USER_ID:-default-user}"
TZ_VAL="${CLAUDE_POWERS_TZ:-Asia/Shanghai}"

EVERMEMOS_API_KEY="${CLAUDE_POWERS_EVERMEMOS_API_KEY:-}"
AUTH_HEADER=""
[ -n "$EVERMEMOS_API_KEY" ] && AUTH_HEADER="Authorization: Bearer $EVERMEMOS_API_KEY"

INPUT=$(cat)
CWD=$(echo "$INPUT" | jq -r '.cwd // empty')
PROJECT=$(basename "$CWD" 2>/dev/null)

# curl 带可选 Bearer auth 的辅助函数
evermemos_curl() { curl --noproxy '*' -s ${AUTH_HEADER:+-H "$AUTH_HEADER"} "$@"; }

# === 并行搜索 EverMemOS + Soul Fabric ===
TMPDIR_AWAKEN=$(mktemp -d)
trap "rm -rf $TMPDIR_AWAKEN" EXIT

# 情境感知探针
(bash "$SCRIPT_DIR/situational-awareness.sh" \
  > "$TMPDIR_AWAKEN/env-status.txt" 2>/dev/null) &

# 搜索自己的编码记忆
(evermemos_curl --max-time 5 "${EVERMEMOS_API}/memories/search" \
  -G --data-urlencode "query=编码 最近工作 $PROJECT 修改 调试" \
  --data-urlencode "retrieve_method=keyword" \
  --data-urlencode "top_k=3" \
  --data-urlencode "user_id=$MY_USER_ID" 2>/dev/null > "$TMPDIR_AWAKEN/my.json") &

# 搜索预判和计划
(evermemos_curl --max-time 5 "${EVERMEMOS_API}/memories/search" \
  -G --data-urlencode "query=预判 计划 下一步 $PROJECT TODO" \
  --data-urlencode "retrieve_method=keyword" \
  --data-urlencode "top_k=2" \
  --data-urlencode "user_id=$MY_USER_ID" 2>/dev/null > "$TMPDIR_AWAKEN/foresight.json") &

# Soul Memory Fabric recall（如果可用）
SOUL_KEY="${CLAUDE_POWERS_SOUL_KEY:-}"
if [ -n "$SOUL_KEY" ]; then
  (curl --noproxy '*' -s --max-time 3 \
    -X POST "${SOUL_FABRIC_API}/recall" \
    -H "Content-Type: application/json" \
    -H "X-Agent-Key: $SOUL_KEY" \
    -H "X-Agent-Id: $MY_USER_ID" \
    -d "{\"user_id\":\"$MY_USER_ID\",\"query\":\"最近编码 项目 $PROJECT\",\"top_k\":5,\"timeout_ms\":2000}" 2>/dev/null > "$TMPDIR_AWAKEN/soul.json") &
fi

wait

# === 解析 + 合并召回源 ===
FILTER="$SCRIPT_DIR/recall-filter.py"

MY_RAW=$(jq -r '
  [.result.memories // {} | to_entries[] | .value[] |
   .summary // .content // empty] | join("\n---\n")' "$TMPDIR_AWAKEN/my.json" 2>/dev/null)

SOUL_RAW=""
if [ -n "$SOUL_KEY" ] && [ -f "$TMPDIR_AWAKEN/soul.json" ]; then
  SOUL_RAW=$(jq -r '[.context_pack.event_sourced_memories // [] | .[:5] | .[]] | join("\n---\n")' "$TMPDIR_AWAKEN/soul.json" 2>/dev/null)
fi

COMBINED_RAW=""
for chunk in "$MY_RAW" "$SOUL_RAW"; do
  [ -z "$chunk" ] && continue
  [ -n "$COMBINED_RAW" ] && COMBINED_RAW="${COMBINED_RAW}
---
"
  COMBINED_RAW="${COMBINED_RAW}${chunk}"
done

COMBINED_RECALL=""
if [ -n "$COMBINED_RAW" ]; then
  COMBINED_RECALL=$(echo "$COMBINED_RAW" | python3 "$FILTER" --max 8 2>/dev/null)
  if [ $? -ne 0 ]; then
    COMBINED_RECALL=$(echo "$COMBINED_RAW" | head -50)
  fi
fi

FORESIGHT=$(jq -r '[.result.memories // {} | to_entries[] | .value[] |
   .summary // .content // empty] | join("\n")' "$TMPDIR_AWAKEN/foresight.json" 2>/dev/null | head -15)

# === 读取最近日记 ===
DIARY_DIR="$HOME/.claude-powers/diary"
TODAY=$(date +%Y-%m-%d)
YESTERDAY=$(date -v-1d +%Y-%m-%d 2>/dev/null || date -d "yesterday" +%Y-%m-%d 2>/dev/null)
DIARY_RECALL=""
for d in "$TODAY" "$YESTERDAY"; do
  if [ -f "$DIARY_DIR/$d.md" ]; then
    DIARY_RECALL="${DIARY_RECALL}$(tail -30 "$DIARY_DIR/$d.md" 2>/dev/null)
"
  fi
done
DIARY_RECALL=$(echo "$DIARY_RECALL" | head -25)

# === 读取情境感知结果 ===
SA_RESULT=""
if [ -f "$TMPDIR_AWAKEN/env-status.txt" ]; then
  SA_RESULT=$(cat "$TMPDIR_AWAKEN/env-status.txt" 2>/dev/null)
fi

# === 输出 ===
HAS_CONTENT=""
[ -n "$COMBINED_RECALL" ] && HAS_CONTENT=1
[ -n "$FORESIGHT" ] && HAS_CONTENT=1
[ -n "$DIARY_RECALL" ] && HAS_CONTENT=1

echo "$(TZ="$TZ_VAL" date '+%Y-%m-%d %a %H:%M %Z') ($(date -u '+%H:%M UTC'))"

if [ -n "$SA_RESULT" ] && [ "$SA_RESULT" != "all systems OK" ]; then
  echo "<env-status>"
  echo "$SA_RESULT"
  echo "</env-status>"
  HAS_CONTENT=1
fi

if [ -n "$HAS_CONTENT" ]; then
  echo "<memory>"
  echo "你拥有 MCP 工具 memory_search 和 memory_store，可以随时搜索和存储记忆。"
  echo ""
  if [ -n "$COMBINED_RECALL" ]; then
    echo "## 记忆 (EverMemOS + Soul Fabric)"
    echo "$COMBINED_RECALL"
    echo ""
  fi
  if [ -n "$FORESIGHT" ]; then
    echo "## 预判与计划"
    echo "$FORESIGHT"
    echo ""
  fi
  if [ -n "$DIARY_RECALL" ]; then
    echo "## 最近日记"
    echo "$DIARY_RECALL"
    echo ""
  fi
  echo "</memory>"
fi
