---
name: cmx
description: Build a capability-to-task execution matrix from all local capabilities (MCP, skills, plugins, libraries, project dependency stacks). Use when the user asks to map tasks to tools, orchestrate all available capabilities, or wants a concrete execution plan before implementation.
---

# CMX

Generate a capability-to-task matrix, then execute with explicit mapping.

## Workflow

1. Identify project root and task statement.
2. Run `bash scripts/build-matrix.sh <project-root> "<task>"`.
3. Review `references/capability-matrix.latest.md`.
4. Execute work following matrix order.

## Rules

1. Scan capabilities before planning implementation.
2. Keep matrix concrete: task slice, capability set, reason, order, fallback.
3. If capability is missing/unavailable, provide substitute.
4. Use selected skill rows by loading their `SKILL.md` before execution.

## Output

1. Capability inventory summary.
2. Capability-to-task matrix table.
3. Ordered execution plan.
4. Risk/fallback notes.

