#!/bin/bash
# 情境感知探针 — 负面报告原则：一切正常时只输出 "all systems OK"

ENV_FILE="$HOME/.claude-powers.env"
source "$ENV_FILE" 2>/dev/null

EVERMEMOS_HOST="${CLAUDE_POWERS_EVERMEMOS_HOST:-127.0.0.1}"
EVERMEMOS_PORT="${CLAUDE_POWERS_EVERMEMOS_PORT:-8001}"
SOUL_HOST="${CLAUDE_POWERS_SOUL_HOST:-127.0.0.1}"
SOUL_PORT="${CLAUDE_POWERS_SOUL_PORT:-12393}"

ISSUES=()

# === 服务健康探针（并行，2s 超时）===
TMPDIR_SA=$(mktemp -d)
trap "rm -rf $TMPDIR_SA" EXIT

check_http() {
  local name=$1 host=$2 port=$3 path=$4 level=$5
  if ! curl --noproxy '*' -sf --max-time 2 "http://${host}:${port}${path}" >/dev/null 2>&1; then
    echo "${level} down: ${name}(:${port})" > "$TMPDIR_SA/${name}.txt"
  fi
}

check_http "EverMemOS" "$EVERMEMOS_HOST" "$EVERMEMOS_PORT" "/health" "CRIT" &
check_http "SoulFabric" "$SOUL_HOST" "$SOUL_PORT" "/health" "WARN" &

wait

# 收集探针结果
for f in "$TMPDIR_SA"/*.txt; do
  [ -f "$f" ] && ISSUES+=("$(cat "$f")")
done

# === 记忆文件新鲜度 ===
# 查找当前用户的 memory 目录
ENCODED_HOME=$(echo "$HOME" | sed 's|/|-|g')
MEMORY_DIR="$HOME/.claude/projects/${ENCODED_HOME}/memory"

check_freshness() {
  local file=$1 days=$2
  local filepath="${MEMORY_DIR}/${file}"
  if [ -f "$filepath" ]; then
    local mod_epoch
    mod_epoch=$(stat -f %m "$filepath" 2>/dev/null || stat -c %Y "$filepath" 2>/dev/null)
    if [ -n "$mod_epoch" ]; then
      local now_epoch
      now_epoch=$(date +%s)
      local age_days=$(( (now_epoch - mod_epoch) / 86400 ))
      if [ "$age_days" -gt "$days" ]; then
        echo "Stale: ${file}(${age_days}d)"
      fi
    fi
  fi
}

STALE_MEM=$(check_freshness "MEMORY.md" 60)
[ -n "$STALE_MEM" ] && ISSUES+=("$STALE_MEM")

# === 输出 ===
if [ ${#ISSUES[@]} -eq 0 ]; then
  echo "all systems OK"
else
  printf '%s\n' "${ISSUES[@]}"
fi
