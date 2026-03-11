---
name: keybag
description: Use when setting up .env files, debugging missing API keys, rotating credentials, deploying new environments, or encountering authentication failures (401, 403, invalid_api_key, redirect_uri_mismatch). Also use when user says "配置密钥", "key", "钥匙包", "env setup"
---

# Keybag — 统一密钥管理

## Overview

所有密钥集中存放在 `~/Desktop/credentials/`，本技能负责查找、注入、验证密钥。**绝不在技能文件中存储密钥明文。**

## 密钥仓库结构

```
~/Desktop/credentials/
├── api-keys.md                    # DeepSeek, SiliconFlow, Google/GitHub OAuth
├── ling-all-keys.txt              # Stripe, X/Twitter, Cloudflare, Relay, Telegram, OpenClaw
├── claude-relay-config.txt        # Anthropic Relay (瑞鹏账号)
├── miku-relay-config.txt          # Anthropic Relay (Miku账号)
├── google-oauth-ling-platform.json # Google OAuth JSON (灵)
├── google-oauth-miku-workspace.json # Google OAuth JSON (Miku)
├── ssh-key.txt                    # SSH 密钥
└── add-ssh-key-command.txt        # SSH 配置命令
```

## 密钥 → 项目映射

| 密钥类型 | 项目 | 源文件 | .env 变量名 |
|----------|------|--------|-------------|
| Google OAuth | Studio | api-keys.md | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| Google OAuth | Ling | api-keys.md | `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` |
| GitHub OAuth | Studio | api-keys.md | `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` |
| GitHub OAuth | Ling | api-keys.md | `GITHUB_OAUTH_CLIENT_ID`, `GITHUB_OAUTH_CLIENT_SECRET` |
| DeepSeek | Ling | api-keys.md | `DEEPSEEK_API_KEY` |
| SiliconFlow | Studio | api-keys.md | `SILICONFLOW_API_KEY` |
| Stripe Live | Studio | ling-all-keys.txt | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` |
| Stripe Live | Ling | ling-all-keys.txt | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `STRIPE_RESTRICTED_KEY` |
| Stripe Prices | Studio | ling-all-keys.txt | `STRIPE_PRICE_*` (6 个) |
| Stripe Prices | Ling | ling-all-keys.txt | `STRIPE_PRICE_*` (5 个) |
| Stripe Links | Ling | ling-all-keys.txt | `STRIPE_LINK_*` (5 个) |
| X/Twitter | Ling (@Ling_Sngxai) | ling-all-keys.txt | `X_API_KEY`, `X_API_SECRET`, `X_ACCESS_TOKEN`, `X_ACCESS_TOKEN_SECRET`, `X_BEARER_TOKEN`, `X_CLIENT_ID`, `X_CLIENT_SECRET` |
| Anthropic Relay | 全局 | claude-relay-config.txt | `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN` |
| Cloudflare | 全局 (sngxai.com) | ling-all-keys.txt | `CLOUDFLARE_EMAIL`, `CLOUDFLARE_GLOBAL_API_KEY`, `CLOUDFLARE_ZONE_ID`, `CLOUDFLARE_ACCOUNT_ID` |
| OpenClaw Gateway | 全局 | ling-all-keys.txt | `GATEWAY_AUTH_TOKEN` |
| Telegram Bot | 全局 | ling-all-keys.txt | `TELEGRAM_BOT_TOKEN` |

## 自动存储规则（强制执行）

**触发条件**：会话中出现以下任一情况时，必须自动执行存储流程：

1. **新建 API key** — 在控制台创建、API 返回、或用户粘贴了新密钥
2. **密钥轮换** — 旧 key 失效，生成了新 key
3. **新增 OAuth** — 配置了新的 OAuth client (Google/GitHub/WeChat/其他)
4. **新增服务** — 接入新的第三方 API (如新的图像/视频/TTS provider)
5. **用户给出密钥** — 用户在对话中提供了任何 key/secret/token

**自动存储流程**：

```
检测到新密钥
    ↓
① 判断归属 → 哪个项目？哪个服务？
    ↓
② 选择目标文件：
   - OAuth 类 → api-keys.md
   - Stripe/X/Cloudflare/基础设施 → ling-all-keys.txt
   - 新服务商 → api-keys.md (追加新 section)
   - SSH/证书 → 独立文件
    ↓
③ 写入 credentials 目录（追加或更新）
   格式：
   ## 服务名
   - 用途：简要说明
   - Key: `新key值`
   - 旧 Key (已撤销): `旧key值`（如有）
   - 控制台: URL（如有）
   - 更新日期: YYYY-MM-DD
    ↓
④ 同步注入 .env（如果能确定目标项目）
   - grep 检查是否已存在 → sed 替换或 echo 追加
    ↓
⑤ 告知用户：存了什么、存在哪里、注入了哪个 .env
```

**不需要用户指示**——检测到新密钥就自动执行。存完后简短汇报。

**绝不遗漏**：如果会话中出现了密钥但没有存储，这是 bug。

## 操作流程

### 1. 查找密钥

```bash
# 按关键词搜索
grep -ri "STRIPE" ~/Desktop/credentials/
grep -ri "OAUTH" ~/Desktop/credentials/
grep -ri "siliconflow" ~/Desktop/credentials/
```

### 2. 注入到 .env

```bash
# 读取源文件，提取目标变量，写入 .env
# 示例：从 ling-all-keys.txt 提取 Studio 的 Stripe 密钥
grep "^STRIPE_" ~/Desktop/credentials/ling-all-keys.txt | head -2
# 然后追加或替换到项目 .env
```

**注入前必须**：
1. 先 `grep` 目标 .env 检查是否已存在该变量
2. 已存在则用 `sed` 替换，不存在则 `echo >>` 追加
3. 注入后验证：`grep "VARIABLE_NAME" .env`

### 3. 验证密钥有效性

```bash
# Stripe
curl -s https://api.stripe.com/v1/balance -u "$STRIPE_SECRET_KEY:" | head -5

# OpenAI
curl -s https://api.openai.com/v1/models -H "Authorization: Bearer $OPENAI_API_KEY" | head -5

# SiliconFlow
curl -s https://api.siliconflow.cn/v1/models -H "Authorization: Bearer $SILICONFLOW_API_KEY" | head -5

# Google OAuth — 用 gcp-oauth-manage 技能

# Cloudflare
curl -s "https://api.cloudflare.com/client/v4/zones/$CLOUDFLARE_ZONE_ID" \
  -H "X-Auth-Email: $CLOUDFLARE_EMAIL" \
  -H "X-Auth-Key: $CLOUDFLARE_GLOBAL_API_KEY" | python3 -c "import sys,json; print(json.load(sys.stdin).get('success'))"
```

### 4. 密钥轮换

轮换后更新源文件 `~/Desktop/credentials/` 中的值，旧 key 标记为 `已撤销`：
```markdown
- Key: `新key`
- 旧 Key (已撤销): `旧key`
- 更新日期: YYYY-MM-DD
```

## 项目 .env 位置

| 项目 | .env 路径 |
|------|----------|
| AI Creative Studio | `~/Projects/ai-creative-studio/.env` |
| Ling Platform | `~/Projects/ling-platform/.env` |
| EverMemOS | `~/Projects/evermemos/.env` |
| OpenClaw | `~/Projects/openclaw/.env` |
| Meme Factory | `~/Projects/ling-meme-factory/.env` |

## 安全规则

1. **绝不** 将密钥写入技能文件、MEMORY.md、或任何 git tracked 文件
2. **绝不** 在终端 echo 完整密钥——截断显示 `${KEY:0:20}...`
3. **绝不** commit .env 文件——确认 .gitignore 包含 `.env`
4. 密钥轮换后立即更新 credentials 目录的源文件
5. 发现密钥泄露：立即撤销 → 生成新 key → 更新源文件 → 更新所有 .env
