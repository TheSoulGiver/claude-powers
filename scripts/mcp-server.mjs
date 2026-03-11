#!/usr/bin/env node

// EPIPE 保护：Claude Code 并行工具调用时可能提前关闭 stdin/stdout 管道
process.stdout.on('error', (err) => {
  if (err.code === 'EPIPE') process.exit(0);
  throw err;
});
process.stdin.on('error', (err) => {
  if (err.code === 'EPIPE') process.exit(0);
  throw err;
});

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";
import { readFileSync } from "fs";
import { homedir } from "os";

// 从 ~/.claude-powers.env 读取配置
function loadEnv() {
  const config = {};
  try {
    const envContent = readFileSync(`${homedir()}/.claude-powers.env`, "utf-8");
    for (const line of envContent.split("\n")) {
      const match = line.match(/^export\s+(\w+)="?([^"]*)"?$/);
      if (match) config[match[1]] = match[2];
    }
  } catch {}
  return config;
}

const ENV = loadEnv();

const EVERMEMOS_API = `http://${ENV.CLAUDE_POWERS_EVERMEMOS_HOST || "127.0.0.1"}:${ENV.CLAUDE_POWERS_EVERMEMOS_PORT || "8001"}/api/v1`;
const SOUL_FABRIC_API = `http://${ENV.CLAUDE_POWERS_SOUL_HOST || "127.0.0.1"}:${ENV.CLAUDE_POWERS_SOUL_PORT || "12393"}/v1/memory`;
const MY_USER_ID = ENV.CLAUDE_POWERS_USER_ID || "default-user";
const EVERMEMOS_API_KEY = ENV.CLAUDE_POWERS_EVERMEMOS_API_KEY || "";
const SOUL_AGENT_KEY = ENV.CLAUDE_POWERS_SOUL_KEY || "";

function everMemHeaders() {
  const h = { "Content-Type": "application/json" };
  if (EVERMEMOS_API_KEY) h["Authorization"] = `Bearer ${EVERMEMOS_API_KEY}`;
  return h;
}

const server = new McpServer({
  name: "memory-bridge",
  version: "1.0.0",
  description: "EverMemOS + Soul Fabric 记忆桥接"
});

// Tool 1: 搜索记忆
server.tool(
  "memory_search",
  "搜索 EverMemOS 中的记忆。默认搜自己的记忆。",
  {
    query: z.string().describe("搜索关键词或语义描述"),
    method: z.enum(["keyword", "vector", "hybrid"]).default("hybrid").describe("搜索方式: keyword=精确匹配, vector=语义相似, hybrid=两者结合(推荐)"),
    top_k: z.number().default(5).describe("返回结果数量"),
    scope: z.enum(["self", "all"]).default("self").describe("搜索范围: self=自己的记忆, all=所有")
  },
  async ({ query, method, top_k, scope }) => {
    try {
      const userIds = scope === "all" ? [MY_USER_ID] : [MY_USER_ID];

      async function searchUser(uid) {
        const memories = [];
        const params = new URLSearchParams({
          query, retrieve_method: method, top_k: String(top_k), user_id: uid
        });
        const res = await fetch(`${EVERMEMOS_API}/memories/search?${params}`, {
          headers: everMemHeaders(),
          signal: AbortSignal.timeout(8000)
        });
        if (!res.ok) return memories;
        let data;
        try { data = await res.json(); } catch { return memories; }
        const memList = data.result?.memories || [];
        for (const memGroup of Array.isArray(memList) ? memList : [memList]) {
          if (!memGroup || typeof memGroup !== "object") continue;
          for (const [type, items] of Object.entries(memGroup)) {
            if (!Array.isArray(items)) continue;
            for (const item of items) {
              memories.push(`[${uid}/${type}] ${item.summary || item.content || ""}`);
            }
          }
        }
        const pendingList = data.result?.pending_messages || [];
        const queryLower = query.toLowerCase();
        for (const msg of pendingList) {
          const content = msg.content || "";
          if (content.toLowerCase().includes(queryLower)) {
            memories.push(`[${uid}/pending:${msg.group_id || "unknown"}] ${content}`);
          }
        }
        return memories;
      }

      const results = await Promise.all(userIds.map(uid =>
        searchUser(uid).catch(() => [])
      ));
      const allMemories = results.flat();

      return { content: [{ type: "text", text: allMemories.length ? allMemories.join("\n---\n") : "没有找到相关记忆。" }] };
    } catch (e) {
      return { content: [{ type: "text", text: `记忆搜索失败: ${e.message}` }], isError: true };
    }
  }
);

// Tool 2: 存储记忆
server.tool(
  "memory_store",
  "将重要信息存入 EverMemOS。",
  {
    content: z.string().describe("要记住的内容"),
    group_id: z.string().default("coding-experience").describe("记忆分组: coding-experience, decision, lesson, discovery"),
    sender_name: z.string().default("Claude Code").describe("调用方名称")
  },
  async ({ content, group_id, sender_name }) => {
    const results = [];
    const now = Date.now();
    const salienceMap = { lesson: 0.8, decision: 0.7, discovery: 0.7, "coding-experience": 0.5 };
    const salience = salienceMap[group_id] || 0.5;

    // 1. 写入 EverMemOS
    try {
      const res = await fetch(`${EVERMEMOS_API}/memories`, {
        method: "POST",
        headers: everMemHeaders(),
        body: JSON.stringify({
          message_id: `cc_store_${now}`,
          create_time: new Date().toISOString(),
          sender: MY_USER_ID,
          sender_name,
          content,
          role: "assistant",
          group_id: `${group_id}_${now}`,
          user_id: MY_USER_ID,
          force_extract: true
        }),
        signal: AbortSignal.timeout(15000)
      });
      const data = await res.json();
      results.push(data.status === "ok" ? "EverMemOS: OK" : `EverMemOS: ${JSON.stringify(data)}`);
    } catch (e) {
      results.push(`EverMemOS: ${e.message}`);
    }

    // 2. 高价值分类自动双写 Soul Fabric
    if (SOUL_AGENT_KEY && ["lesson", "decision", "discovery"].includes(group_id)) {
      try {
        const memTypeMap = { lesson: "semantic", decision: "semantic", discovery: "episode" };
        const res = await fetch(`${SOUL_FABRIC_API}/events`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Agent-Key": SOUL_AGENT_KEY,
            "X-Agent-Id": MY_USER_ID
          },
          body: JSON.stringify({
            idempotency_key: `cc_store_${now}_${Math.random().toString(36).slice(2, 8)}`,
            user_id: MY_USER_ID,
            content_raw: content,
            source: "claude-code",
            memory_type: memTypeMap[group_id] || "semantic",
            salience,
            agent_id: MY_USER_ID
          }),
          signal: AbortSignal.timeout(15000)
        });
        results.push(res.ok ? "Soul Fabric: OK" : `Soul Fabric: ${res.status}`);
      } catch (e) {
        results.push(`Soul Fabric: ${e.message}`);
      }
    }
    return { content: [{ type: "text", text: results.join("\n") || "已记住。" }] };
  }
);

// Tool 3: 显式存储到 Soul Memory Fabric
server.tool(
  "soul_store",
  "将重要记忆写入 Soul Memory Fabric。用于记录关键决策、调试发现、架构教训等高价值信息。自动双写 EverMemOS。",
  {
    content: z.string().describe("要记住的内容"),
    memory_type: z.enum(["episode", "semantic", "procedural"]).default("episode").describe("记忆类型: episode=事件经历, semantic=知识概念, procedural=操作步骤"),
    salience: z.number().min(0).max(1).default(0.7).describe("重要性 0-1: 0.4=普通, 0.7=重要, 0.9=关键"),
    sender_name: z.string().default("Claude Code").describe("调用方名称")
  },
  async ({ content, memory_type, salience, sender_name }) => {
    const results = [];
    const now = Date.now();

    if (SOUL_AGENT_KEY) {
      try {
        const res = await fetch(`${SOUL_FABRIC_API}/events`, {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "X-Agent-Key": SOUL_AGENT_KEY,
            "X-Agent-Id": MY_USER_ID
          },
          body: JSON.stringify({
            idempotency_key: `cc_soul_${now}_${Math.random().toString(36).slice(2, 8)}`,
            user_id: MY_USER_ID,
            content_raw: content,
            source: "claude-code",
            memory_type,
            salience,
            agent_id: MY_USER_ID
          }),
          signal: AbortSignal.timeout(15000)
        });
        results.push(res.ok ? "Soul Fabric: OK" : `Soul Fabric: ${res.status}`);
      } catch (e) {
        results.push(`Soul Fabric: ${e.message}`);
      }
    } else {
      results.push("Soul Fabric: 无 SOUL_AGENT_KEY，跳过");
    }

    // EverMemOS 双写
    try {
      const res = await fetch(`${EVERMEMOS_API}/memories`, {
        method: "POST",
        headers: everMemHeaders(),
        body: JSON.stringify({
          message_id: `cc_soul_${now}`,
          create_time: new Date().toISOString(),
          sender: MY_USER_ID,
          sender_name,
          content,
          role: "assistant",
          group_id: "coding-experience",
          user_id: MY_USER_ID,
          force_extract: true
        }),
        signal: AbortSignal.timeout(15000)
      });
      const data = await res.json();
      results.push(data.status === "ok" ? "EverMemOS: OK" : `EverMemOS: ${JSON.stringify(data)}`);
    } catch (e) {
      results.push(`EverMemOS: ${e.message}`);
    }
    return { content: [{ type: "text", text: results.join("\n") }] };
  }
);

// Tool 4: 系统状态
server.tool(
  "system_status",
  "查看 EverMemOS 和 Soul Fabric 连接状态。",
  {},
  async () => {
    const checks = [];
    try {
      const em = await fetch(`${EVERMEMOS_API.replace('/api/v1', '')}/health`, {
        signal: AbortSignal.timeout(3000)
      }).then(r => r.ok ? "running" : "error").catch(() => "unreachable");
      checks.push(`EverMemOS: ${em}`);
    } catch {
      checks.push("EverMemOS: unreachable");
    }
    try {
      const sf = await fetch(`${SOUL_FABRIC_API.replace('/v1/memory', '')}/health`, {
        signal: AbortSignal.timeout(3000)
      }).then(r => r.ok ? "running" : "error").catch(() => "unreachable");
      checks.push(`Soul Fabric: ${sf}`);
    } catch {
      checks.push("Soul Fabric: unreachable");
    }
    return { content: [{ type: "text", text: checks.join("\n") }] };
  }
);

const transport = new StdioServerTransport();
await server.connect(transport);
