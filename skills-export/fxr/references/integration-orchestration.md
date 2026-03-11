# Integration Orchestration

Use this guide to coordinate all frontend-related local capabilities.

## 1. Build the Capability Inventory

Always include these sections:

1. MCP servers:
   - global MCP from `~/.claude.json`
   - project MCP from `~/.claude.json` project scope
   - user MCP from `~/.claude/.mcp.json`
   - workspace MCP from `<project-root>/.mcp.json` when present
2. Skills and plugins:
   - user skills in `~/.claude/skills`
   - marketplace skills under `~/.claude/plugins/marketplaces`
3. Component libraries:
   - declared and installed UI dependencies from active `package.json`

## 2. Capability-to-Task Mapping

Map each task to one primary capability and optional backup:

1. Visual direction and layout language -> frontend-design style skills.
2. Screenshot verification loops -> webapp testing or screenshot-related tools.
3. UI framework implementation -> component-library matrix assignment.
4. Accessibility/performance checks -> relevant testing or build tools.

## 3. Invocation Order

Run in this sequence:

1. capability discovery
2. baseline screenshots
3. design token definition
4. component-library assignment
5. implementation iterations with screenshot loop
6. quality-gate verification

## 4. Rational Multi-Library Usage

When the user requires full use of installed libraries:

1. assign ownership by page or feature area
2. avoid mixing equivalent components in the same surface
3. unify styles with shared tokens and adapter wrappers
4. document why each library is used

## 5. Fallback Rules

If a capability is unavailable:

1. state missing capability
2. provide equivalent tool/skill
3. continue without blocking the overhaul

