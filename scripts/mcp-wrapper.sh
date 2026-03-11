#!/bin/bash
# MCP Server 启动包装器 — 清理代理变量，防止代理干扰 localhost 请求
export NO_PROXY="localhost,127.0.0.1,::1"
export no_proxy="localhost,127.0.0.1,::1"
unset ALL_PROXY all_proxy HTTP_PROXY http_proxy HTTPS_PROXY https_proxy

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# 自动检测 node 路径
NODE_BIN=$(which node 2>/dev/null)
if [ -z "$NODE_BIN" ]; then
  # 尝试 nvm 路径
  NVM_NODE=$(ls -d "$HOME/.nvm/versions/node"/*/bin/node 2>/dev/null | tail -1)
  NODE_BIN="${NVM_NODE:-/usr/local/bin/node}"
fi

exec "$NODE_BIN" "$SCRIPT_DIR/mcp-server.mjs" 2>>/tmp/mcp-memory-bridge.log
