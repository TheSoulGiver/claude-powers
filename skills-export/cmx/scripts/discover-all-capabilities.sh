#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${1:-$(pwd)}"
HOME_DIR="${HOME:-/Users/caoruipeng}"
CLAUDE_DIR="$HOME_DIR/.claude"
CODEX_DIR="$HOME_DIR/.codex"

if [[ ! -d "$PROJECT_DIR" ]]; then
  echo "Error: project directory does not exist: $PROJECT_DIR" >&2
  exit 1
fi

echo "# Capability Inventory"
echo "Generated: $(date '+%Y-%m-%d %H:%M:%S %z')"
echo "Project: $PROJECT_DIR"
echo

echo "## MCP Servers (All Sources)"
python3 - "$PROJECT_DIR" "$HOME_DIR" <<'PY'
import json
import pathlib
import sys

project = pathlib.Path(sys.argv[1]).resolve()
home = pathlib.Path(sys.argv[2]).resolve()
claude_json_path = home / ".claude.json"
claude_user_mcp = home / ".claude" / ".mcp.json"
project_mcp = project / ".mcp.json"
codex_toml = home / ".codex" / "config.toml"

rows = []

def add(scope, name, source, command="", mtype="", note=""):
    rows.append({
        "scope": scope,
        "name": name or "(unnamed)",
        "source": str(source),
        "command": command or "",
        "type": mtype or "",
        "note": note or "",
    })

def read_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def compact_command(cfg):
    cmd = cfg.get("command", "")
    args = cfg.get("args", [])
    if not isinstance(args, list):
        args = []
    return " ".join([x for x in [cmd, *args] if x]).strip()

cfg = read_json(claude_json_path)
if cfg:
    for name, m in (cfg.get("mcpServers") or {}).items():
        if isinstance(m, dict):
            add("claude-global", name, claude_json_path, compact_command(m), m.get("type", ""))

    projects = cfg.get("projects") or {}
    project_cfg = projects.get(str(project))
    if project_cfg is None:
        candidates = [k for k in projects.keys() if str(project).startswith(k) or k.startswith(str(project))]
        if candidates:
            candidates.sort(key=len, reverse=True)
            project_cfg = projects[candidates[0]]
    if isinstance(project_cfg, dict):
        for name, m in (project_cfg.get("mcpServers") or {}).items():
            if isinstance(m, dict):
                add("claude-project", name, claude_json_path, compact_command(m), m.get("type", ""))

u = read_json(claude_user_mcp)
if u:
    for name, m in (u.get("mcpServers") or {}).items():
        if isinstance(m, dict):
            add("claude-user", name, claude_user_mcp, compact_command(m), m.get("type", ""))

p = read_json(project_mcp)
if p:
    for name, m in (p.get("mcpServers") or {}).items():
        if isinstance(m, dict):
            add("project-mcp-json", name, project_mcp, compact_command(m), m.get("type", ""))

# Parse codex TOML for potential MCP declarations.
if codex_toml.exists():
    text = codex_toml.read_text()
    if "mcp" in text.lower():
        try:
            import tomllib
            parsed = tomllib.loads(text)
        except Exception:
            parsed = {}

        mcp_servers = parsed.get("mcp_servers")
        if isinstance(mcp_servers, dict):
            for name, m in mcp_servers.items():
                if isinstance(m, dict):
                    cmd = m.get("command", "")
                    args = m.get("args", [])
                    if not isinstance(args, list):
                        args = []
                    command = " ".join([x for x in [cmd, *args] if x]).strip()
                    add("codex-config-toml", str(name), codex_toml, command, m.get("type", ""))

        # Fallback parser for Python versions without tomllib or non-standard TOML.
        if not isinstance(mcp_servers, dict):
            import ast
            current = None
            simple = {}
            for raw in text.splitlines():
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if line.startswith("[mcp_servers.") and line.endswith("]"):
                    current = line[len("[mcp_servers.") : -1].strip()
                    simple[current] = {}
                    continue
                if current and "=" in line:
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip()
                    try:
                        parsed_v = ast.literal_eval(v)
                    except Exception:
                        parsed_v = v.strip('"').strip("'")
                    simple[current][k] = parsed_v
            for name, m in simple.items():
                cmd = m.get("command", "")
                args = m.get("args", [])
                if not isinstance(args, list):
                    args = []
                command = " ".join([x for x in [cmd, *args] if x]).strip()
                add("codex-config-toml", str(name), codex_toml, command, m.get("type", ""))

        # Generic fallback: report mcp-related keys even if non-standard.
        def walk(obj, path):
            if isinstance(obj, dict):
                for k, v in obj.items():
                    p = f"{path}.{k}" if path else k
                    if "mcp" in str(k).lower():
                        add("codex-config-toml", p, codex_toml, note=f"value-type={type(v).__name__}")
                    walk(v, p)
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    walk(v, f"{path}[{i}]")
        walk(parsed, "")

if not rows:
    print("- (no MCP servers found)")
    sys.exit(0)

seen = set()
unique = []
for r in rows:
    key = (r["scope"], r["name"], r["source"], r["command"], r["type"], r["note"])
    if key in seen:
        continue
    seen.add(key)
    unique.append(r)

unique.sort(key=lambda r: (r["scope"], r["name"], r["source"]))
for r in unique:
    line = f"- [{r['scope']}] {r['name']}"
    if r["type"]:
        line += f" ({r['type']})"
    if r["command"]:
        line += f" -> {r['command']}"
    elif r["note"]:
        line += f" -> {r['note']}"
    print(line)
    print(f"  source: {r['source']}")
PY

echo
echo "## Skills (All Sources)"
python3 - "$HOME_DIR" <<'PY'
import pathlib
import re
import sys

home = pathlib.Path(sys.argv[1]).resolve()
roots = [
    home / ".codex" / "skills",
    home / ".claude" / "skills",
    home / ".claude" / "plugins",
    home / ".codex" / "vendor_imports" / "skills",
]

skills = []

def classify(path: pathlib.Path):
    p = str(path)
    codex = str(home / ".codex")
    claude = str(home / ".claude")
    if p.startswith(f"{codex}/skills/.system/"):
        return "codex-system"
    if p.startswith(f"{codex}/skills/"):
        return "codex-user"
    if p.startswith(f"{claude}/skills/"):
        return "claude-user"
    if p.startswith(f"{claude}/plugins/marketplaces/"):
        return "claude-plugin-marketplace"
    if p.startswith(f"{claude}/plugins/cache/"):
        return "claude-plugin-cache"
    if p.startswith(f"{codex}/vendor_imports/skills/"):
        return "codex-vendor-import"
    return "other"

def parse_skill(path: pathlib.Path):
    text = path.read_text(errors="ignore")
    name = path.parent.name
    desc = ""
    m = re.match(r"^---\n(.*?)\n---", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if line.startswith("name:"):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("description:"):
                desc = line.split(":", 1)[1].strip()
    return name, desc

for root in roots:
    if not root.exists():
        continue
    for f in root.rglob("SKILL.md"):
        try:
            name, desc = parse_skill(f)
        except Exception:
            name, desc = (f.parent.name, "")
        skills.append({
            "name": name,
            "desc": desc,
            "path": str(f),
            "source": classify(f),
        })

if not skills:
    print("- (no skills found)")
    sys.exit(0)

skills.sort(key=lambda x: (x["source"], x["name"], x["path"]))

counts = {}
for s in skills:
    counts[s["source"]] = counts.get(s["source"], 0) + 1

for source in sorted(counts):
    print(f"- {source}: {counts[source]}")

print()
for s in skills:
    print(f"- [{s['source']}] {s['name']} :: {s['path']}")
PY

echo
echo "## Package Capability Sets (All Known Project Roots)"
python3 - "$PROJECT_DIR" "$HOME_DIR" <<'PY'
import json
import pathlib
import re
import sys

project = pathlib.Path(sys.argv[1]).resolve()
home = pathlib.Path(sys.argv[2]).resolve()
claude_json = home / ".claude.json"

CAP_RE = re.compile(
    r"(react|next|vue|nuxt|svelte|angular|remix|gatsby|solid|"
    r"mui|material|chakra|antd|base-ui|fluent|radix|headless|mantine|"
    r"tailwind|bootstrap|bulma|emotion|styled|fontsource|"
    r"storybook|vite|webpack|rollup|parcel|esbuild|"
    r"playwright|cypress|vitest|jest|eslint|typescript)",
    re.IGNORECASE,
)

roots = {project}

def add_if_pkg(root):
    pkg = root / "package.json"
    if pkg.exists():
        roots.add(root)

add_if_pkg(home)

if claude_json.exists():
    try:
        cfg = json.loads(claude_json.read_text())
    except Exception:
        cfg = {}
    for p in (cfg.get("projects") or {}).keys():
        rp = pathlib.Path(p)
        if rp.exists():
            add_if_pkg(rp)

projects_dir = home / "Projects"
if projects_dir.exists():
    for p in projects_dir.glob("*"):
        if p.is_dir():
            add_if_pkg(p)
        if p.is_dir():
            for pp in p.glob("*"):
                if pp.is_dir():
                    add_if_pkg(pp)

rows = []
for root in sorted(roots):
    pkg = root / "package.json"
    if not pkg.exists():
        continue
    try:
        data = json.loads(pkg.read_text())
    except Exception:
        continue
    deps = {}
    for k in ("dependencies", "devDependencies", "peerDependencies"):
        d = data.get(k) or {}
        if isinstance(d, dict):
            deps.update(d)
    if not deps:
        continue

    caps = sorted([k for k in deps.keys() if CAP_RE.search(k)])
    rows.append({
        "root": str(root),
        "total": len(deps),
        "caps": caps,
        "deps": deps,
    })

if not rows:
    print("- (no package capability sets found)")
    sys.exit(0)

for r in rows:
    print(f"- {r['root']}")
    print(f"  total-deps: {r['total']}")
    if r["caps"]:
        preview = ", ".join([f"{k}@{r['deps'].get(k, '')}" for k in r["caps"]])
        print(f"  capability-deps: {preview}")
    else:
        print("  capability-deps: (none matched)")
PY

echo
echo "## Other Local Capability Sources"
echo "- Codex rules:"
find "$CODEX_DIR/rules" -type f 2>/dev/null | sed 's/^/  - /' || true
echo "- AGENTS.md files (home + projects, trimmed):"
{
  find "$HOME_DIR" -maxdepth 3 -type f -name 'AGENTS.md' 2>/dev/null || true
  find "$HOME_DIR/Projects" -maxdepth 4 -type f -name 'AGENTS.md' 2>/dev/null || true
} | sort -u | sed 's/^/  - /'
echo "- Key executables:"
for bin in codex claude node npm npx git rg; do
  path="$(command -v "$bin" 2>/dev/null || true)"
  if [[ -n "$path" ]]; then
    echo "  - $bin -> $path"
  fi
done
