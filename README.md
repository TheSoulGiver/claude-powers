# Claude Powers

为 Claude Code CLI 一键配置完整的 Skills + Memory + Hooks + MCP + 后端记忆系统。

## 快速安装

```bash
git clone https://github.com/TheSoulGiver/claude-powers.git
cd claude-powers
nano config.env          # 填写你的名字和 API key
chmod +x setup.sh
./setup.sh               # 一键安装
```

安装完成后：
```bash
~/.claude-powers/infra/start-services.sh start   # 启动后端服务
claude                                             # 开始使用
```

## 系统架构

```
Claude Code
  ├── Skills (5 个通用技能)
  ├── Memory Files (MEMORY.md 自动加载到上下文)
  ├── Hooks
  │   ├── SessionStart  → 从 EverMemOS 加载记忆
  │   ├── UserPromptSubmit → 注入真实时间
  │   ├── SessionEnd    → LLM 摘要写入 EverMemOS
  │   ├── PreCompact    → 压缩前保存关键上下文
  │   ├── Stop          → 总结 + 存记忆
  │   └── PreToolUse    → 防止误杀 Claude 进程
  │
  └── MCP Server → EverMemOS (localhost:8001)
                 → Soul Fabric (localhost:12393)

Docker 基础设施
  ├── MongoDB 7.0      (:27017)  ← 两个服务共享
  ├── Elasticsearch 8   (:19200) ← EverMemOS 全文搜索
  ├── Milvus 2.5        (:19530) ← EverMemOS 向量搜索
  └── Redis 7.2         (:6380)  ← EverMemOS 缓存

本地应用
  ├── EverMemOS (Python/FastAPI, :8001)  ← 长期记忆系统
  ├── Soul Fabric (Python/FastAPI, :12393) ← 灵魂记忆
  └── Ollama + qwen3-embedding (:11434)  ← 向量化模型
```

## 安装步骤

### 前置条件

```bash
# 必须
brew install node jq python3 git
brew install --cask docker    # Docker Desktop

# Claude Code
npm install -g @anthropic-ai/claude-code

# Python 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 本地 embedding 模型
brew install ollama
ollama pull qwen3-embedding
```

### 第 1 步：准备源码

需要从瑞鹏的 Mac 复制两个项目的源码：

```bash
# 在安装包目录下创建 source 目录
mkdir -p source

# 方法 A: 通过 AirDrop / U盘
# 把瑞鹏 Mac 上的以下目录复制到这里:
# ~/.openclaw/workspace/EverMemOS/ → source/EverMemOS/
# ~/soul-memory-fabric/           → source/soul-memory-fabric/

# 方法 B: 通过 scp（同一网络）
scp -r caoruipeng@<瑞鹏IP>:~/.openclaw/workspace/EverMemOS ./source/EverMemOS
scp -r caoruipeng@<瑞鹏IP>:~/soul-memory-fabric ./source/soul-memory-fabric
```

### 第 2 步：编辑配置

```bash
nano config.env
```

必须填写：
- `USER_NAME` — 你的名字
- `USER_ID` — 英文标识（如 `xiaoli`）
- `ANTHROPIC_API_KEY` — 你的 Anthropic API key

### 第 3 步：运行安装

```bash
chmod +x setup.sh
./setup.sh
```

### 第 4 步：启动服务

```bash
# 启动所有后端服务（Docker + EverMemOS + Soul Fabric）
~/.claude-powers/infra/start-services.sh start

# 检查状态
~/.claude-powers/infra/start-services.sh status
```

### 第 5 步：启动 Claude Code

```bash
claude
```

首次启动会自动下载 plugins（需要网络）。

## 日常使用

```bash
# 每天开机后启动服务
~/.claude-powers/infra/start-services.sh start

# 然后正常使用 Claude Code
claude

# 关机前停止服务（可选，Docker Desktop 关闭会自动停止）
~/.claude-powers/infra/start-services.sh stop
```

## 文件结构

```
安装后:
~/.claude/
├── settings.json           # 全局配置（模型、插件）
├── settings.local.json     # 本机配置（权限、hooks）
├── .mcp.json               # MCP server 注册
├── skills/                 # 自定义技能
│   ├── browser-test/
│   ├── cmx/
│   ├── fxr/
│   ├── keybag/
│   └── masters-council/
└── projects/<encoded-home>/memory/
    ├── MEMORY.md           # 主索引（自动加载）
    ├── projects.md
    └── preferences.md

~/.claude-powers/
├── scripts/                # Hook 脚本 + MCP server
├── infra/                  # Docker compose + 服务管理
├── EverMemOS/              # EverMemOS 应用源码
├── soul-memory-fabric/     # Soul Fabric 应用源码
├── diary/                  # 每日编码日记
├── logs/                   # 服务日志
├── pids/                   # 进程 PID 文件
└── CREDENTIALS.txt         # 生成的密钥

~/.claude-powers.env        # 运行时环境变量
```

## 磁盘空间需求

| 组件 | 大小 |
|------|------|
| Docker 镜像 | ~5GB |
| Docker 数据卷（初始） | ~500MB |
| EverMemOS 源码 + 依赖 | ~1GB |
| Soul Fabric | ~100MB |
| Ollama qwen3-embedding | ~1.5GB |
| **总计** | **~8GB** |

## 故障排除

### Docker 容器启动失败
```bash
cd ~/.claude-powers/infra
docker compose logs <service-name>
```

### EverMemOS 无法启动
```bash
# 检查日志
cat ~/.claude-powers/logs/evermemos.log

# 常见问题: MongoDB 未就绪，等几秒后重试
~/.claude-powers/infra/start-services.sh restart
```

### 向量搜索不工作
```bash
# 确保 Ollama 在运行
ollama serve &
ollama list  # 应该看到 qwen3-embedding
```

### Claude Code 启动时报 MCP 错误
```bash
# 检查 MCP server 日志
cat /tmp/mcp-memory-bridge.log

# 确保 node_modules 已安装
cd ~/.claude-powers/scripts && npm install
```

## 卸载

```bash
# 停止服务
~/.claude-powers/infra/start-services.sh stop

# 删除 Docker 数据
cd ~/.claude-powers/infra && docker compose down -v

# 删除所有文件
rm -rf ~/.claude-powers
rm ~/.claude-powers.env

# 恢复 Claude Code 配置
cp ~/.claude/settings.local.json.bak ~/.claude/settings.local.json
cp ~/.claude/.mcp.json.bak ~/.claude/.mcp.json
```
