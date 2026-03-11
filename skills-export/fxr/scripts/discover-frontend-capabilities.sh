#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
HOME_DIR="${HOME:-/Users/caoruipeng}"
CLAUDE_DIR="$HOME_DIR/.claude"
CLAUDE_CONFIG="$HOME_DIR/.claude.json"
USER_MCP_CONFIG="$CLAUDE_DIR/.mcp.json"
WORKSPACE_MCP_CONFIG="$PROJECT_DIR/.mcp.json"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Error: project directory does not exist: $PROJECT_DIR" >&2
  exit 1
fi

echo "# Frontend Capability Inventory"
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "Project: $PROJECT_DIR"
echo

echo "## MCP Servers"
node - "$PROJECT_DIR" "$CLAUDE_CONFIG" "$USER_MCP_CONFIG" "$WORKSPACE_MCP_CONFIG" <<'NODE'
const fs = require("fs");
const path = require("path");

const projectDir = process.argv[2];
const claudeConfigPath = process.argv[3];
const userMcpPath = process.argv[4];
const workspaceMcpPath = process.argv[5];

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (err) {
    return null;
  }
}

function compactCommand(cfg = {}) {
  const cmd = cfg.command || "";
  const args = Array.isArray(cfg.args) ? cfg.args.join(" ") : "";
  return `${cmd}${args ? " " + args : ""}`.trim();
}

const rows = [];

const claudeConfig = readJson(claudeConfigPath);
if (claudeConfig) {
  const global = claudeConfig.mcpServers || {};
  for (const [name, cfg] of Object.entries(global)) {
    rows.push({
      scope: "global",
      name,
      source: claudeConfigPath,
      command: compactCommand(cfg),
      type: cfg.type || "",
    });
  }

  const projects = claudeConfig.projects || {};
  const exact = projects[projectDir];
  const closestKey = Object.keys(projects)
    .filter((p) => projectDir.startsWith(p) || p.startsWith(projectDir))
    .sort((a, b) => b.length - a.length)[0];
  const projectConfig = exact || (closestKey ? projects[closestKey] : null);

  if (projectConfig && projectConfig.mcpServers) {
    for (const [name, cfg] of Object.entries(projectConfig.mcpServers)) {
      rows.push({
        scope: "project",
        name,
        source: claudeConfigPath,
        command: compactCommand(cfg),
        type: cfg.type || "",
      });
    }
  }
}

const userMcp = readJson(userMcpPath);
if (userMcp && userMcp.mcpServers) {
  for (const [name, cfg] of Object.entries(userMcp.mcpServers)) {
    rows.push({
      scope: "user",
      name,
      source: userMcpPath,
      command: compactCommand(cfg),
      type: cfg.type || "",
    });
  }
}

const workspaceMcp = readJson(workspaceMcpPath);
if (workspaceMcp && workspaceMcp.mcpServers) {
  for (const [name, cfg] of Object.entries(workspaceMcp.mcpServers)) {
    rows.push({
      scope: "workspace",
      name,
      source: workspaceMcpPath,
      command: compactCommand(cfg),
      type: cfg.type || "",
    });
  }
}

if (!rows.length) {
  console.log("- (none found)");
  process.exit(0);
}

rows
  .sort((a, b) =>
    `${a.scope}:${a.name}`.localeCompare(`${b.scope}:${b.name}`)
  )
  .forEach((row) => {
    const command = row.command || "(no command)";
    const type = row.type ? ` (${row.type})` : "";
    console.log(`- [${row.scope}] ${row.name}${type} -> ${command}`);
    console.log(`  source: ${row.source}`);
  });
NODE

echo
echo "## Frontend-Related Skills"
{
  find "$CLAUDE_DIR/skills" -type f -name "SKILL.md" 2>/dev/null || true
  find "$CLAUDE_DIR/plugins/marketplaces" -type f -name "SKILL.md" 2>/dev/null || true
} | sort -u | while IFS= read -r skill_file; do
  [[ -f "$skill_file" ]] || continue

  skill_name="$(awk -F': ' '/^name: /{print $2; exit}' "$skill_file" 2>/dev/null || true)"
  skill_desc="$(awk -F': ' '/^description: /{print $2; exit}' "$skill_file" 2>/dev/null || true)"

  haystack="$skill_name $skill_desc"
  if printf '%s' "$haystack" | rg -qi 'frontend|webapp|website|landing page|ui|ux|react|chakra|mui|antd|fluent|base-ui|design system|theme|css|component|accessibility|a11y|playwright|mcp'; then
    echo "- ${skill_name:-unknown} :: $skill_file"
  fi
done

echo
echo "## Active Project UI Libraries"
"$SCRIPT_DIR/check-ui-stack.sh" "$PROJECT_DIR"

echo
echo "## Known Project Roots With Frontend Dependencies"
node - "$CLAUDE_CONFIG" <<'NODE'
const fs = require("fs");
const path = require("path");

const claudeConfigPath = process.argv[2];
const FE_RE = /(^react$|react-dom|react-is|mui|emotion|styled-components|antd|chakra|base-ui|fluentui|fontsource|tailwind|next-themes|react-icons)/i;

function readJson(file) {
  try {
    return JSON.parse(fs.readFileSync(file, "utf8"));
  } catch (err) {
    return null;
  }
}

const cfg = readJson(claudeConfigPath);
if (!cfg || !cfg.projects) {
  console.log("- (no project metadata found)");
  process.exit(0);
}

const roots = Object.keys(cfg.projects);
let found = 0;

for (const root of roots) {
  const pkgPath = path.join(root, "package.json");
  if (!fs.existsSync(pkgPath)) continue;

  let pkg;
  try {
    pkg = JSON.parse(fs.readFileSync(pkgPath, "utf8"));
  } catch (err) {
    continue;
  }

  const deps = {
    ...(pkg.dependencies || {}),
    ...(pkg.devDependencies || {}),
    ...(pkg.peerDependencies || {}),
  };
  const keys = Object.keys(deps).filter((k) => FE_RE.test(k)).sort();
  if (!keys.length) continue;

  found += 1;
  console.log(`- ${root}`);
  console.log(`  libs: ${keys.join(", ")}`);
}

if (!found) {
  console.log("- (no frontend dependency sets found)");
}
NODE
