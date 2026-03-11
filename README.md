# Claude Powers

> [OpenClaw](https://github.com/openclaw) + [Claude Code](https://docs.anthropic.com/en/docs/claude-code) 超能力系统 — 三层记忆架构，让你的 Claude Code 拥有跨会话长期记忆。

Claude Powers 是 **OpenClaw 生态系统**的记忆与技能基础设施，专为 Claude Code CLI 设计。它将 OpenClaw 的 [EverMemOS](source/EverMemOS/) 企业级记忆系统和 [Soul Memory Fabric](source/soul-memory-fabric/) 灵魂记忆引擎整合进 Claude Code 的 Hooks + MCP 体系，实现：

- 会话间的长期记忆持久化
- 自动化的记忆生命周期管理
- 可扩展的技能系统

## What is this?

**OpenClaw** 是一个 AI Agent 运行时平台。**Claude Code** 是 Anthropic 的 CLI 编码助手。Claude Powers 将两者连接：

```
┌──────────────────────────────────────────────────┐
│                 OpenClaw Ecosystem                │
│                                                  │
│  EverMemOS ──── 企业级记忆系统 (语义搜索/向量检索)  │
│  Soul Fabric ── 灵魂记忆引擎 (高价值决策/教训存储)  │
│                                                  │
├──────────────────────────────────────────────────┤
│              Claude Powers (本项目)               │
│                                                  │
│  Hooks ──────── 6 个生命周期钩子 (唤醒/入眠/保护)  │
│  MCP Server ─── 记忆桥接 (search/store/recall)   │
│  Skills ─────── 5 个可调用技能                    │
│  Memory Files ─ 三层记忆文件系统                   │
│                                                  │
├──────────────────────────────────────────────────┤
│               Claude Code CLI                    │
│                                                  │
│  你的日常编码助手，现在拥有了长期记忆               │
└──────────────────────────────────────────────────┘
```

## Features

- **三层记忆架构** — Memory Files (零延迟) → EverMemOS (语义搜索) → Soul Fabric (深度存储)
- **自动记忆生命周期** — 唤醒加载 → 对话中积累 → 入眠摘要 → 压缩保护，全自动
- **时间感知** — 每条消息注入真实时间，Claude 永远知道"现在几点"
- **上下文保护** — 长会话压缩前自动保存关键上下文，防止中途失忆
- **进程保护** — PreToolUse Hook 阻止 Claude 误杀自己的进程
- **OpenClaw MCP 桥接** — `memory_search`、`memory_store`、`soul_store`、`system_status`
- **5 个 Skills** — browser-test / cmx / fxr / keybag / masters-council

## Quick Start

### 1. 安装前置依赖

```bash
# macOS (Homebrew)
brew install node jq python3 git
brew install --cask docker

# Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Python 包管理器
curl -LsSf https://astral.sh/uv/install.sh | sh

# 本地 Embedding 模型（向量搜索需要）
brew install ollama
ollama pull qwen3-embedding
```

### 2. Clone & 配置

```bash
git clone https://github.com/TheSoulGiver/claude-powers.git
cd claude-powers
```

编辑 `config.env`：

```bash
nano config.env
```

必须填写 3 项：

| 字段 | 说明 | 示例 |
|------|------|------|
| `USER_NAME` | 你的名字 | `"小明"` |
| `USER_ID` | 英文标识（唯一） | `"xiaoming"` |
| `ANTHROPIC_API_KEY` | Anthropic API Key | `"sk-ant-..."` |

### 3. 一键安装

```bash
chmod +x setup.sh
./setup.sh
```

安装脚本会自动完成：
- 启动 Docker 基础设施（MongoDB / Elasticsearch / Milvus / Redis）
- 安装 EverMemOS 和 Soul Memory Fabric
- 配置 Hook 脚本和 MCP Server
- 安装 Skills 和 Memory 模板
- 生成所有密钥和配置文件

### 4. 启动 & 使用

```bash
# 启动后端服务
~/.claude-powers/infra/start-services.sh start

# 查看服务状态
~/.claude-powers/infra/start-services.sh status

# 开始使用 Claude Code
claude
```

## Three-Layer Memory System

Claude Powers 使用三层记忆架构，每层有不同的速度、容量和用途：

```
┌─────────────────────────────────────────────────────────────────┐
│                        Claude Code 对话                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Layer 1: Memory Files (零延迟，每次自动加载)                     │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ ~/.claude/projects/<path>/memory/                         │  │
│  │   MEMORY.md ← 主索引，自动注入对话上下文 (200行以内)        │  │
│  │   projects.md, preferences.md ← 按需 Read 加载            │  │
│  │                                                           │  │
│  │ 特点: 纯 Markdown, 无延迟, Claude 直接读写                  │  │
│  │ 适合: 核心规则、项目索引、用户偏好、关键教训                   │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │ Read/Write                       │
│                              ▼                                  │
│  Layer 2: EverMemOS (语义搜索，跨会话持久化)                      │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ localhost:8001 — Python/FastAPI                            │  │
│  │                                                           │  │
│  │ 存储: MongoDB (文档) + Elasticsearch (全文) + Milvus (向量) │  │
│  │ 能力: keyword / vector / hybrid 三种检索模式                │  │
│  │ 接口: MCP 工具 memory_search / memory_store                │  │
│  │                                                           │  │
│  │ 特点: LLM 自动提取关键信息, 语义去重, 按 group 分类          │  │
│  │ 适合: 编码经历、项目上下文、会话摘要、跨天记忆                 │  │
│  └───────────────────────────────────────────────────────────┘  │
│                              │ 高价值自动双写                     │
│                              ▼                                  │
│  Layer 3: Soul Memory Fabric (深度存储，高价值决策)                │
│  ┌───────────────────────────────────────────────────────────┐  │
│  │ localhost:12393 — Python/FastAPI                           │  │
│  │                                                           │  │
│  │ 存储: MongoDB (独立数据库 soul_memory)                      │  │
│  │ 数据结构: MemoryAtom (带 salience/confidence/trust 评分)    │  │
│  │ 接口: MCP 工具 soul_store                                  │  │
│  │                                                           │  │
│  │ 特点: 显式重要性标注 (0-1), 记忆类型分类, 审计追踪           │  │
│  │ 适合: 架构决策、调试教训、关键发现、不可遗忘的经验             │  │
│  └───────────────────────────────────────────────────────────┘  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Memory Lifecycle

记忆在会话生命周期中的完整流转：

```
                         ┌──────────────┐
                         │  启动 Claude  │
                         └──────┬───────┘
                                │
                    ┌───────────▼───────────┐
                    │   SessionStart Hook   │
                    │     (awaken.sh)       │
                    └───────────┬───────────┘
                                │
              ┌─────────────────┼─────────────────┐
              │                 │                  │
              ▼                 ▼                  ▼
    ┌────────────────┐ ┌──────────────┐ ┌──────────────────┐
    │ EverMemOS 搜索  │ │ Soul Fabric  │ │ 读取本地日记文件   │
    │ (keyword, 3路)  │ │   recall     │ │ (today/yesterday) │
    └───────┬────────┘ └──────┬───────┘ └────────┬─────────┘
            │                 │                   │
            └─────────┬───────┘                   │
                      ▼                           │
            ┌──────────────────┐                  │
            │ recall-filter.py │                  │
            │ 去重+压缩+限8条   │                  │
            └────────┬─────────┘                  │
                     │                            │
                     └──────────┬─────────────────┘
                                ▼
                    ┌───────────────────────┐
                    │  注入 <memory> 到上下文 │
                    └───────────┬───────────┘
                                │
                    ┌───────────▼───────────┐
                    │      对话进行中...      │
                    └───────────┬───────────┘
                                │
               ┌────────────────┼────────────────┐
               │                │                 │
    ┌──────────▼──────────┐    │     ┌───────────▼───────────┐
    │ UserPromptSubmit     │    │     │ PreCompact Hook       │
    │ (inject-time.sh)     │    │     │ 压缩前保存关键上下文    │
    │ 每条消息注入真实时间   │    │     │ → EverMemOS + Soul    │
    └─────────────────────┘    │     └───────────────────────┘
                               │
               ┌───────────────┼───────────────┐
               │                               │
    ┌──────────▼──────────┐        ┌───────────▼───────────┐
    │ Claude 主动调用 MCP  │        │    Stop / SessionEnd   │
    │ memory_store (发现)  │        │     (sleep.sh)         │
    │ soul_store (决策)    │        └───────────┬───────────┘
    └─────────────────────┘                    │
                                               ▼
                                   ┌───────────────────────┐
                                   │ Haiku LLM 生成150字摘要 │
                                   └───────────┬───────────┘
                                               │
                              ┌────────────────┼────────────────┐
                              │                │                │
                              ▼                ▼                ▼
                    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
                    │  EverMemOS   │ │ Soul Fabric  │ │  本地日记     │
                    │ (force写入)   │ │ (episode)    │ │ diary/mm-dd  │
                    └──────────────┘ └──────────────┘ └──────────────┘
```

## Architecture

```
Claude Code CLI
  │
  ├── Skills ─────────── 5 个可调用技能 (browser-test, cmx, fxr, keybag, masters-council)
  ├── Memory Files ───── MEMORY.md 自动加载到每次对话上下文 (Layer 1)
  │
  ├── Hooks (6 个生命周期钩子)
  │   ├── SessionStart     → awaken.sh    从 Layer 2+3 加载记忆到上下文
  │   ├── UserPromptSubmit → inject-time  注入真实时间戳
  │   ├── SessionEnd       → sleep.sh     LLM 摘要 → 三写 (Layer 2 + 3 + diary)
  │   ├── PreCompact       → prompt       压缩前保存关键上下文到 Layer 2+3
  │   ├── Stop             → prompt       总结 + 存教训到 Layer 2
  │   └── PreToolUse       → guard.sh     阻止误杀 Claude 进程
  │
  └── MCP Server (memory-bridge)
      ├── memory_search    搜索 Layer 2 (EverMemOS)
      ├── memory_store     写入 Layer 2（高价值自动双写 Layer 3）
      ├── soul_store       显式写入 Layer 3 (Soul Fabric)
      └── system_status    检查所有服务健康状态

Docker Infrastructure (全部空容器，首次安装零数据)
  ├── MongoDB 7.0       :27017   文档存储（EverMemOS db:memsys + Soul db:soul_memory）
  ├── Elasticsearch 8   :19200   全文关键词搜索
  ├── Milvus 2.5        :19530   向量语义搜索
  ├── MinIO + etcd               Milvus 对象存储 + 协调
  └── Redis 7.2         :6380    缓存队列

Local Applications
  ├── EverMemOS         :8001    Layer 2 — 长期记忆 (Python/FastAPI)
  ├── Soul Fabric       :12393   Layer 3 — 灵魂记忆 (Python/FastAPI)
  └── Ollama            :11434   Embedding 模型 (qwen3-embedding, 1024维)
```

## Daily Usage

```bash
# 开机后启动（约 30 秒）
~/.claude-powers/infra/start-services.sh start

# 正常使用 Claude Code
claude

# 关机前停止（可选）
~/.claude-powers/infra/start-services.sh stop
```

**Claude 会自动：**
- 启动时搜索相关记忆加载到上下文
- 每条消息注入当前真实时间
- 长会话压缩前保存关键信息
- 会话结束时生成摘要写入 EverMemOS
- 遇到重要发现时通过 MCP 工具主动存储

## Installed File Structure

```
~/.claude/
├── settings.json                     全局配置（模型、插件）
├── settings.local.json               权限、Hooks、语言
├── .mcp.json                         MCP Server 注册
├── skills/                           自定义技能
│   ├── browser-test/                   AI 浏览器测试
│   ├── cmx/                            能力矩阵构建
│   ├── fxr/                            前端重构编排
│   ├── keybag/                         密钥管理
│   └── masters-council/                大师参谋团
└── projects/<encoded-home>/memory/
    ├── MEMORY.md                       主索引（每次自动加载）
    ├── projects.md                     项目记录
    └── preferences.md                  用户偏好

~/.claude-powers/
├── scripts/              Hook 脚本 + MCP Server + Node 依赖
├── infra/                Docker Compose + 服务启停脚本
├── EverMemOS/            EverMemOS 应用
├── soul-memory-fabric/   Soul Fabric 应用
├── diary/                每日编码日记（自动写入）
├── logs/                 服务日志
└── CREDENTIALS.txt       自动生成的密钥

~/.claude-powers.env      运行时环境变量
```

## Disk Space

| 组件 | 大小 |
|------|------|
| Docker 镜像 | ~5 GB |
| Docker 数据卷（初始） | ~500 MB |
| EverMemOS + 依赖 | ~1 GB |
| Soul Fabric | ~100 MB |
| Ollama qwen3-embedding | ~1.5 GB |
| **总计** | **~8 GB** |

## Troubleshooting

<details>
<summary><b>Docker 容器启动失败</b></summary>

```bash
cd ~/.claude-powers/infra
docker compose logs mongodb        # 查看具体服务日志
docker compose logs elasticsearch
```
</details>

<details>
<summary><b>EverMemOS 无法启动</b></summary>

```bash
cat ~/.claude-powers/logs/evermemos.log

# 常见原因：MongoDB 还没就绪，重启试试
~/.claude-powers/infra/start-services.sh restart
```
</details>

<details>
<summary><b>向量搜索不工作</b></summary>

```bash
# 确保 Ollama 在运行
ollama serve &
ollama list   # 应该看到 qwen3-embedding
```
</details>

<details>
<summary><b>Claude Code 报 MCP 错误</b></summary>

```bash
cat /tmp/mcp-memory-bridge.log
cd ~/.claude-powers/scripts && npm install
```
</details>

## Uninstall

```bash
~/.claude-powers/infra/start-services.sh stop
cd ~/.claude-powers/infra && docker compose down -v
rm -rf ~/.claude-powers ~/.claude-powers.env
cp ~/.claude/settings.local.json.bak ~/.claude/settings.local.json
cp ~/.claude/.mcp.json.bak ~/.claude/.mcp.json
```

## License

Personal & non-commercial use only. See [LICENSE](LICENSE).

## Part of OpenClaw Ecosystem

Claude Powers 是 [OpenClaw](https://github.com/openclaw) AI Agent 生态系统的一部分：

| 组件 | 说明 |
|------|------|
| **OpenClaw** | AI Agent 运行时平台 — 社交调度、多 Agent 协作 |
| **EverMemOS** | 企业级记忆系统 — 语义搜索、向量检索、LLM 提取 |
| **Soul Memory Fabric** | 灵魂记忆引擎 — 高价值决策存储、审计追踪、记忆进化 |
| **Claude Powers** (本项目) | Claude Code 集成层 — Hooks + MCP + Skills |

## Credits

Built for the [OpenClaw](https://github.com/openclaw) ecosystem.
Powered by [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Anthropic](https://anthropic.com).
