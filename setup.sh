#!/bin/bash
set -euo pipefail

# ============================================================
# Claude Powers 一键安装脚本（完整本地部署版）
# Skills + Memory + Hooks + MCP + EverMemOS + Soul Fabric
# ============================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
CLAUDE_DIR="$HOME/.claude"
POWERS_DIR="$HOME/.claude-powers"

echo "========================================="
echo "  Claude Powers 完整安装程序"
echo "========================================="
echo ""

# === 第 0 步：检查依赖 ===
echo "[0/10] 检查依赖..."

MISSING=()
command -v node >/dev/null 2>&1 || MISSING+=("node")
command -v npm >/dev/null 2>&1 || MISSING+=("npm")
command -v jq >/dev/null 2>&1 || MISSING+=("jq")
command -v python3 >/dev/null 2>&1 || MISSING+=("python3")
command -v docker >/dev/null 2>&1 || MISSING+=("docker")
command -v git >/dev/null 2>&1 || MISSING+=("git")

WARN=()
command -v claude >/dev/null 2>&1 || WARN+=("claude (Claude Code CLI)")
command -v uv >/dev/null 2>&1 || WARN+=("uv (Python package manager)")
command -v ollama >/dev/null 2>&1 || WARN+=("ollama (本地 embedding 模型)")

if [ ${#MISSING[@]} -gt 0 ]; then
  echo "  缺少必要工具: ${MISSING[*]}"
  echo ""
  echo "  安装方式:"
  echo "    brew install node jq python3 git"
  echo "    brew install --cask docker"
  exit 1
fi

echo "  必要依赖已满足"

if [ ${#WARN[@]} -gt 0 ]; then
  echo "  可选工具未安装: ${WARN[*]}"
  echo "  安装方式:"
  command -v claude >/dev/null 2>&1 || echo "    Claude Code: npm install -g @anthropic-ai/claude-code"
  command -v uv >/dev/null 2>&1 || echo "    uv: curl -LsSf https://astral.sh/uv/install.sh | sh"
  command -v ollama >/dev/null 2>&1 || echo "    ollama: brew install ollama"
fi

# === 第 1 步：读取配置 ===
echo ""
echo "[1/10] 读取配置..."

CONFIG_FILE="$SCRIPT_DIR/config.env"
if [ ! -f "$CONFIG_FILE" ]; then
  echo "  错误: 找不到 config.env，请先编辑配置文件。"
  exit 1
fi

source_config() {
  local key=$1
  grep "^${key}=" "$CONFIG_FILE" | head -1 | cut -d'"' -f2
}

USER_NAME=$(source_config "USER_NAME")
USER_ID=$(source_config "USER_ID")
ANTHROPIC_API_KEY=$(source_config "ANTHROPIC_API_KEY")
ANTHROPIC_BASE_URL=$(source_config "ANTHROPIC_BASE_URL")
TIMEZONE=$(source_config "TIMEZONE")
DEFAULT_MODEL=$(source_config "DEFAULT_MODEL")

# 本地部署，所有服务都在 localhost
EVERMEMOS_HOST="127.0.0.1"
EVERMEMOS_PORT="8001"
SOUL_FABRIC_HOST="127.0.0.1"
SOUL_FABRIC_PORT="12393"

if [ "$USER_NAME" = "你的名字" ] || [ "$USER_ID" = "your-username" ]; then
  echo "  错误: 请先编辑 config.env 填写你的信息！"
  exit 1
fi

echo "  用户: $USER_NAME ($USER_ID)"
echo "  时区: $TIMEZONE"
echo "  模式: 完整本地部署"

# 生成随机密钥
EVERMEMOS_API_KEY=$(openssl rand -base64 32 | tr -d '/+=' | head -c 44)
SOUL_AGENT_KEY=$(openssl rand -hex 24)
JWT_SECRET=$(openssl rand -hex 32)

# === 第 2 步：创建目录结构 ===
echo ""
echo "[2/10] 创建目录结构..."

mkdir -p "$CLAUDE_DIR/skills"
mkdir -p "$POWERS_DIR"/{scripts,diary,logs,pids,infra}

ENCODED_HOME=$(echo "$HOME" | sed 's|/|-|g')
MEMORY_DIR="$CLAUDE_DIR/projects/${ENCODED_HOME}/memory"
mkdir -p "$MEMORY_DIR"

echo "  $POWERS_DIR/"
echo "  $MEMORY_DIR/"

# === 第 3 步：部署 Docker 基础设施 ===
echo ""
echo "[3/10] 部署 Docker 基础设施..."

cp "$SCRIPT_DIR/infra/docker-compose.yaml" "$POWERS_DIR/infra/"
chmod +x "$SCRIPT_DIR/infra/start-services.sh"
cp "$SCRIPT_DIR/infra/start-services.sh" "$POWERS_DIR/infra/"

# 检查 Docker 是否在运行
if ! docker info >/dev/null 2>&1; then
  echo "  Docker 未运行。请先启动 Docker Desktop，然后重新运行此脚本。"
  echo "  或者安装后手动运行: cd $POWERS_DIR/infra && docker compose up -d"
  DOCKER_STARTED=0
else
  cd "$POWERS_DIR/infra"
  docker compose up -d 2>&1 | sed 's/^/  /'
  DOCKER_STARTED=1
  echo "  Docker 基础设施已启动"
fi

# === 第 4 步：安装 EverMemOS ===
echo ""
echo "[4/10] 安装 EverMemOS..."

EVERMEMOS_DIR="$POWERS_DIR/EverMemOS"
if [ -d "$SCRIPT_DIR/source/EverMemOS" ]; then
  # 如果安装包里自带源码
  cp -r "$SCRIPT_DIR/source/EverMemOS" "$EVERMEMOS_DIR"
  echo "  从安装包复制 EverMemOS 源码"
elif [ -d "$EVERMEMOS_DIR" ]; then
  echo "  EverMemOS 已存在，跳过"
else
  echo "  EverMemOS 源码未找到。"
  echo "  请将 EverMemOS 源码目录复制到: $EVERMEMOS_DIR"
  echo "  或放到安装包的 source/EverMemOS/ 目录下重新运行。"
  echo ""
  echo "  复制命令（在瑞鹏的 Mac 上执行）:"
  echo "    scp -r ~/.openclaw/workspace/EverMemOS <你的用户名>@<你的IP>:$EVERMEMOS_DIR"
  EVERMEMOS_INSTALLED=0
fi

if [ -d "$EVERMEMOS_DIR" ]; then
  # 生成 .env
  sed \
    -e "s|__ANTHROPIC_API_KEY__|$ANTHROPIC_API_KEY|g" \
    -e "s|__EVERMEMOS_API_KEY__|$EVERMEMOS_API_KEY|g" \
    -e "s|__JWT_SECRET__|$JWT_SECRET|g" \
    "$SCRIPT_DIR/infra/evermemos.env.template" > "$EVERMEMOS_DIR/.env"

  # 安装 Python 依赖
  cd "$EVERMEMOS_DIR"
  if command -v uv >/dev/null 2>&1; then
    uv sync 2>&1 | tail -1 | sed 's/^/  /'
  else
    echo "  需要 uv 来安装依赖: curl -LsSf https://astral.sh/uv/install.sh | sh"
  fi
  EVERMEMOS_INSTALLED=1
  echo "  EverMemOS 已安装"
fi

# === 第 5 步：安装 Soul Memory Fabric ===
echo ""
echo "[5/10] 安装 Soul Memory Fabric..."

SOUL_DIR="$POWERS_DIR/soul-memory-fabric"
if [ -d "$SCRIPT_DIR/source/soul-memory-fabric" ]; then
  cp -r "$SCRIPT_DIR/source/soul-memory-fabric" "$SOUL_DIR"
  echo "  从安装包复制 Soul Fabric 源码"
elif [ -d "$SOUL_DIR" ]; then
  echo "  Soul Fabric 已存在，跳过"
else
  echo "  Soul Fabric 源码未找到。"
  echo "  请将源码复制到: $SOUL_DIR"
  echo ""
  echo "  复制命令（在瑞鹏的 Mac 上执行）:"
  echo "    scp -r ~/soul-memory-fabric <你的用户名>@<你的IP>:$SOUL_DIR"
  SOUL_INSTALLED=0
fi

if [ -d "$SOUL_DIR" ]; then
  # 生成 .env
  sed "s|__SOUL_AGENT_KEY__|$SOUL_AGENT_KEY|g" \
    "$SCRIPT_DIR/infra/soul-fabric.env.template" > "$POWERS_DIR/infra/soul-fabric.env"

  cd "$SOUL_DIR"
  pip3 install -e . 2>&1 | tail -1 | sed 's/^/  /'
  SOUL_INSTALLED=1
  echo "  Soul Fabric 已安装"
fi

# === 第 6 步：安装 Ollama embedding 模型 ===
echo ""
echo "[6/10] 配置 Embedding 模型..."

if command -v ollama >/dev/null 2>&1; then
  if ! ollama list 2>/dev/null | grep -q "qwen3-embedding"; then
    echo "  下载 qwen3-embedding 模型（约 1.5GB）..."
    ollama pull qwen3-embedding 2>&1 | tail -3 | sed 's/^/  /'
  else
    echo "  qwen3-embedding 模型已存在"
  fi
else
  echo "  Ollama 未安装，EverMemOS 的向量搜索将不可用。"
  echo "  安装方式: brew install ollama"
  echo "  安装后运行: ollama pull qwen3-embedding"
fi

# === 第 7 步：生成运行时环境文件 ===
echo ""
echo "[7/10] 生成运行时配置..."

cat > "$HOME/.claude-powers.env" << ENVEOF
# Claude Powers 运行时配置（由 setup.sh 生成）
export CLAUDE_POWERS_USER_ID="$USER_ID"
export CLAUDE_POWERS_USER_NAME="$USER_NAME"
export CLAUDE_POWERS_EVERMEMOS_HOST="$EVERMEMOS_HOST"
export CLAUDE_POWERS_EVERMEMOS_PORT="$EVERMEMOS_PORT"
export CLAUDE_POWERS_EVERMEMOS_API_KEY="$EVERMEMOS_API_KEY"
export CLAUDE_POWERS_SOUL_HOST="$SOUL_FABRIC_HOST"
export CLAUDE_POWERS_SOUL_PORT="$SOUL_FABRIC_PORT"
export CLAUDE_POWERS_SOUL_KEY="$SOUL_AGENT_KEY"
export CLAUDE_POWERS_ANTHROPIC_KEY="$ANTHROPIC_API_KEY"
export CLAUDE_POWERS_ANTHROPIC_URL="$ANTHROPIC_BASE_URL"
export CLAUDE_POWERS_TZ="$TIMEZONE"
ENVEOF

echo "  ~/.claude-powers.env"

# === 第 8 步：安装 Hook 脚本 + MCP ===
echo ""
echo "[8/10] 安装 Hook 脚本 + MCP Server..."

cp "$SCRIPT_DIR/scripts/inject-time.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/guard-claude-process.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/awaken.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/sleep.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/preserve.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/situational-awareness.sh" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/recall-filter.py" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/mcp-server.mjs" "$POWERS_DIR/scripts/"
cp "$SCRIPT_DIR/scripts/mcp-wrapper.sh" "$POWERS_DIR/scripts/"

chmod +x "$POWERS_DIR/scripts/"*.sh

# MCP 依赖
cd "$POWERS_DIR/scripts"
if [ ! -f "package.json" ]; then
  cat > package.json << 'PKGEOF'
{
  "name": "claude-powers-mcp",
  "version": "1.0.0",
  "type": "module",
  "dependencies": {
    "@modelcontextprotocol/sdk": "^1.0.0",
    "zod": "^3.22.0"
  }
}
PKGEOF
fi
npm install --silent 2>/dev/null
cd "$SCRIPT_DIR"

echo "  Hook 脚本 + MCP 已安装"

# === 第 9 步：生成 Claude Code 配置 ===
echo ""
echo "[9/10] 生成 Claude Code 配置..."

# settings.json
SETTINGS_FILE="$CLAUDE_DIR/settings.json"
if [ -f "$SETTINGS_FILE" ]; then
  echo "  settings.json 已存在，跳过"
else
  cat > "$SETTINGS_FILE" << SETTINGSEOF
{
  "model": "$DEFAULT_MODEL",
  "enabledPlugins": {
    "superpowers@claude-plugins-official": true,
    "context7@claude-plugins-official": true,
    "commit-commands@claude-plugins-official": true,
    "claude-md-management@claude-plugins-official": true
  }
}
SETTINGSEOF
  echo "  $SETTINGS_FILE"
fi

# settings.local.json
SETTINGS_LOCAL="$CLAUDE_DIR/settings.local.json"
if [ -f "$SETTINGS_LOCAL" ]; then
  cp "$SETTINGS_LOCAL" "${SETTINGS_LOCAL}.bak"
  echo "  已备份 settings.local.json"
fi

cat > "$SETTINGS_LOCAL" << LOCALEOF
{
  "permissions": {
    "allow": [
      "Bash(ls:*)",
      "Bash(find:*)",
      "Bash(grep:*)",
      "Bash(curl:*)",
      "Bash(node:*)",
      "Bash(npm:*)",
      "Bash(npx:*)",
      "Bash(python3:*)",
      "Bash(git:*)",
      "Bash(docker:*)",
      "Bash(pm2:*)",
      "Bash(echo:*)",
      "Bash(head:*)",
      "Bash(tail:*)",
      "Bash(ps:*)",
      "Bash(pgrep:*)",
      "Bash(jq:*)",
      "Bash(wc:*)",
      "Bash(sort:*)",
      "Bash(bash:*)",
      "Bash(chmod:*)",
      "Bash(source:*)",
      "WebSearch",
      "mcp__memory-bridge__memory_search",
      "mcp__memory-bridge__memory_store",
      "mcp__memory-bridge__soul_store",
      "mcp__memory-bridge__system_status"
    ]
  },
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          {
            "type": "command",
            "command": "$POWERS_DIR/scripts/guard-claude-process.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "SessionStart": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$POWERS_DIR/scripts/awaken.sh",
            "timeout": 15
          }
        ]
      }
    ],
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$POWERS_DIR/scripts/inject-time.sh",
            "timeout": 5
          }
        ]
      }
    ],
    "SessionEnd": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "$POWERS_DIR/scripts/sleep.sh",
            "timeout": 30
          }
        ]
      }
    ],
    "PreCompact": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "上下文即将被压缩。先运行 date 获取当前真实时间。然后提取这次对话中最重要的内容：1) 当前真实时间 2) 做了什么改动（文件路径）3) 关键决策及原因 4) 未完成的事项 5) 学到的教训。用中文，简洁列出。",
            "timeout": 15,
            "model": "claude-haiku-4-5-20251001"
          }
        ]
      }
    ],
    "Stop": [
      {
        "hooks": [
          {
            "type": "prompt",
            "prompt": "任务结束。用一句话总结你刚刚完成了什么，以及是否有值得记住的经验教训。如果有重要发现或教训，用 memory_store 工具存入 EverMemOS。用中文。",
            "timeout": 10,
            "model": "claude-haiku-4-5-20251001"
          }
        ]
      }
    ]
  },
  "language": "chinese"
}
LOCALEOF

echo "  $SETTINGS_LOCAL"

# MCP 配置
MCP_FILE="$CLAUDE_DIR/.mcp.json"
if [ -f "$MCP_FILE" ]; then
  cp "$MCP_FILE" "${MCP_FILE}.bak"
fi

cat > "$MCP_FILE" << MCPEOF
{
  "mcpServers": {
    "memory-bridge": {
      "type": "stdio",
      "command": "$POWERS_DIR/scripts/mcp-wrapper.sh",
      "args": []
    }
  }
}
MCPEOF

echo "  $MCP_FILE"

# === 第 10 步：安装 Memory + Skills ===
echo ""
echo "[10/10] 安装 Memory 模板 + Skills..."

if [ ! -f "$MEMORY_DIR/MEMORY.md" ]; then
  sed "s/__USER_NAME__/$USER_NAME/g" "$SCRIPT_DIR/templates/MEMORY.md" > "$MEMORY_DIR/MEMORY.md"
  cp "$SCRIPT_DIR/templates/projects.md" "$MEMORY_DIR/"
  cp "$SCRIPT_DIR/templates/preferences.md" "$MEMORY_DIR/"
  echo "  Memory 模板已安装"
else
  echo "  Memory 文件已存在，跳过"
fi

if [ -d "$SCRIPT_DIR/skills-export" ] && [ "$(ls -A "$SCRIPT_DIR/skills-export" 2>/dev/null)" ]; then
  cp -r "$SCRIPT_DIR/skills-export/"* "$CLAUDE_DIR/skills/" 2>/dev/null || true
  SKILL_COUNT=$(ls -d "$CLAUDE_DIR/skills/"*/ 2>/dev/null | wc -l | tr -d ' ')
  echo "  已安装 $SKILL_COUNT 个 Skills"
fi

# === 保存密钥到文件 ===
cat > "$POWERS_DIR/CREDENTIALS.txt" << CREDEOF
Claude Powers 生成的密钥（请妥善保管）
生成时间: $(date)

EverMemOS API Key: $EVERMEMOS_API_KEY
Soul Agent Key:    $SOUL_AGENT_KEY
JWT Secret:        $JWT_SECRET
CREDEOF

chmod 600 "$POWERS_DIR/CREDENTIALS.txt"

# === 完成 ===
echo ""
echo "========================================="
echo "  安装完成！"
echo "========================================="
echo ""
echo "已安装的组件:"
echo "  [x] Docker 基础设施 (MongoDB, ES, Milvus, Redis)"
echo "  [x] Hook 脚本 (6 个生命周期钩子)"
echo "  [x] MCP Server (memory_search, memory_store, soul_store)"
echo "  [x] Memory 文件系统 (MEMORY.md + 模板)"
echo "  [x] Claude Code 配置 (settings + permissions + hooks)"
if [ "${EVERMEMOS_INSTALLED:-0}" = "1" ]; then
  echo "  [x] EverMemOS (本地)"
else
  echo "  [ ] EverMemOS (需要手动复制源码)"
fi
if [ "${SOUL_INSTALLED:-0}" = "1" ]; then
  echo "  [x] Soul Memory Fabric (本地)"
else
  echo "  [ ] Soul Memory Fabric (需要手动复制源码)"
fi
echo ""
echo "密钥已保存到: $POWERS_DIR/CREDENTIALS.txt"
echo ""
echo "===== 启动服务 ====="
echo ""
echo "  # 启动所有后端服务"
echo "  $POWERS_DIR/infra/start-services.sh start"
echo ""
echo "  # 查看服务状态"
echo "  $POWERS_DIR/infra/start-services.sh status"
echo ""
echo "  # 启动 Claude Code"
echo "  claude"
echo ""
if [ "${EVERMEMOS_INSTALLED:-0}" = "0" ] || [ "${SOUL_INSTALLED:-0}" = "0" ]; then
  echo "===== 还需要手动操作 ====="
  echo ""
  [ "${EVERMEMOS_INSTALLED:-0}" = "0" ] && echo "  1. 复制 EverMemOS 源码到 $EVERMEMOS_DIR"
  [ "${SOUL_INSTALLED:-0}" = "0" ] && echo "  2. 复制 Soul Fabric 源码到 $SOUL_DIR"
  echo "  3. 安装 Ollama + qwen3-embedding: brew install ollama && ollama pull qwen3-embedding"
  echo "  4. 然后重新运行本脚本完成安装"
  echo ""
fi
