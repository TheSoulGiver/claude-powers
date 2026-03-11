#!/bin/bash
set -euo pipefail

# Claude Powers 服务启动脚本
# 用法: ./start-services.sh [start|stop|status|restart]

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
POWERS_DIR="$HOME/.claude-powers"
ACTION="${1:-start}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

case "$ACTION" in
  start)
    echo "=== 启动 Claude Powers 服务 ==="
    echo ""

    # 1. Docker 基础设施
    echo "[1/4] 启动 Docker 基础设施..."
    if ! docker info >/dev/null 2>&1; then
      echo -e "${RED}Docker 未运行！请先启动 Docker Desktop。${NC}"
      exit 1
    fi
    cd "$POWERS_DIR/infra"
    docker compose up -d
    echo -e "${GREEN}  Docker 服务已启动${NC}"

    # 2. 等待 MongoDB 就绪
    echo "[2/4] 等待 MongoDB 就绪..."
    for i in $(seq 1 30); do
      if docker exec claude-powers-mongodb mongosh --quiet --eval "db.runCommand('ping').ok" >/dev/null 2>&1; then
        echo -e "${GREEN}  MongoDB 已就绪${NC}"
        break
      fi
      if [ "$i" -eq 30 ]; then
        echo -e "${RED}  MongoDB 启动超时！${NC}"
        exit 1
      fi
      sleep 1
    done

    # 3. 启动 EverMemOS
    echo "[3/4] 启动 EverMemOS..."
    if [ -d "$POWERS_DIR/EverMemOS" ]; then
      cd "$POWERS_DIR/EverMemOS"
      # 检查是否已在运行
      if pgrep -f "python.*run.py" >/dev/null 2>&1; then
        echo -e "${YELLOW}  EverMemOS 已在运行${NC}"
      else
        nohup uv run python src/run.py --port 8001 > "$POWERS_DIR/logs/evermemos.log" 2>&1 &
        echo $! > "$POWERS_DIR/pids/evermemos.pid"
        sleep 2
        if curl --noproxy localhost -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
          echo -e "${GREEN}  EverMemOS 已启动 (port 8001)${NC}"
        else
          echo -e "${YELLOW}  EverMemOS 启动中，请稍候...${NC}"
        fi
      fi
    else
      echo -e "${RED}  EverMemOS 未安装！请先运行 setup.sh${NC}"
    fi

    # 4. 启动 Soul Memory Fabric
    echo "[4/4] 启动 Soul Memory Fabric..."
    if [ -d "$POWERS_DIR/soul-memory-fabric" ]; then
      cd "$POWERS_DIR/soul-memory-fabric"
      if pgrep -f "uvicorn.*soul_fabric" >/dev/null 2>&1; then
        echo -e "${YELLOW}  Soul Fabric 已在运行${NC}"
      else
        source "$POWERS_DIR/infra/soul-fabric.env" 2>/dev/null || true
        nohup uvicorn soul_fabric.api.routes:app --port 12393 --host 127.0.0.1 > "$POWERS_DIR/logs/soul-fabric.log" 2>&1 &
        echo $! > "$POWERS_DIR/pids/soul-fabric.pid"
        sleep 2
        if curl --noproxy localhost -sf http://127.0.0.1:12393/v1/memory/status >/dev/null 2>&1; then
          echo -e "${GREEN}  Soul Fabric 已启动 (port 12393)${NC}"
        else
          echo -e "${YELLOW}  Soul Fabric 启动中，请稍候...${NC}"
        fi
      fi
    else
      echo -e "${RED}  Soul Fabric 未安装！请先运行 setup.sh${NC}"
    fi

    echo ""
    echo -e "${GREEN}=== 所有服务已启动 ===${NC}"
    ;;

  stop)
    echo "=== 停止 Claude Powers 服务 ==="

    # 停止应用进程
    if [ -f "$POWERS_DIR/pids/evermemos.pid" ]; then
      kill "$(cat "$POWERS_DIR/pids/evermemos.pid")" 2>/dev/null || true
      rm "$POWERS_DIR/pids/evermemos.pid"
      echo "  EverMemOS 已停止"
    fi
    if [ -f "$POWERS_DIR/pids/soul-fabric.pid" ]; then
      kill "$(cat "$POWERS_DIR/pids/soul-fabric.pid")" 2>/dev/null || true
      rm "$POWERS_DIR/pids/soul-fabric.pid"
      echo "  Soul Fabric 已停止"
    fi

    # 也尝试按进程名杀
    pkill -f "python.*run.py.*--port 8001" 2>/dev/null || true
    pkill -f "uvicorn.*soul_fabric" 2>/dev/null || true

    # 停止 Docker
    cd "$POWERS_DIR/infra" 2>/dev/null && docker compose down 2>/dev/null || true
    echo "  Docker 服务已停止"
    echo ""
    echo "=== 所有服务已停止 ==="
    ;;

  status)
    echo "=== Claude Powers 服务状态 ==="
    echo ""

    # Docker
    echo "Docker 容器:"
    docker ps --filter "name=claude-powers" --format "  {{.Names}}: {{.Status}}" 2>/dev/null || echo "  Docker 未运行"
    echo ""

    # EverMemOS
    printf "EverMemOS (8001):  "
    if curl --noproxy localhost -sf http://127.0.0.1:8001/health >/dev/null 2>&1; then
      echo -e "${GREEN}运行中${NC}"
    else
      echo -e "${RED}未运行${NC}"
    fi

    # Soul Fabric
    printf "Soul Fabric (12393): "
    if curl --noproxy localhost -sf http://127.0.0.1:12393/v1/memory/status >/dev/null 2>&1; then
      echo -e "${GREEN}运行中${NC}"
    else
      echo -e "${RED}未运行${NC}"
    fi

    # Ollama
    printf "Ollama (11434):    "
    if curl --noproxy localhost -sf http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      echo -e "${GREEN}运行中${NC}"
    else
      echo -e "${YELLOW}未运行（EverMemOS 向量搜索需要）${NC}"
    fi
    ;;

  restart)
    "$0" stop
    sleep 2
    "$0" start
    ;;

  *)
    echo "用法: $0 {start|stop|status|restart}"
    exit 1
    ;;
esac
