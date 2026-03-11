#!/usr/bin/env python3
import argparse
import re
from pathlib import Path


def uniq_keep_order(items):
    seen = set()
    out = []
    for i in items:
        if not i or i in seen:
            continue
        seen.add(i)
        out.append(i)
    return out


def parse_manifest(text):
    lines = text.splitlines()
    section = None
    mcp = []
    skills = []
    pkg_rows = []
    for ln in lines:
        if ln.startswith("## "):
            section = ln.strip()
            continue

        if section == "## MCP Servers (All Sources)":
            mm = re.match(r"^- \[([^\]]+)\]\s+(.+?)(?:\s+\(|\s+->|$)", ln)
            if mm:
                mcp.append({"scope": mm.group(1).strip(), "name": mm.group(2).strip()})

        elif section == "## Skills (All Sources)":
            mm = re.match(r"^- \[([^\]]+)\]\s+(.+?)\s+::\s+(.+)$", ln)
            if mm:
                skills.append(
                    {
                        "source": mm.group(1).strip(),
                        "name": mm.group(2).strip(),
                        "path": mm.group(3).strip(),
                    }
                )

        elif section == "## Package Capability Sets (All Known Project Roots)":
            mm_root = re.match(r"^- (/.*)$", ln)
            if mm_root:
                pkg_rows.append({"root": mm_root.group(1).strip(), "deps": []})
                continue
            mm_deps = re.match(r"^\s+capability-deps:\s+(.*)$", ln)
            if mm_deps and pkg_rows:
                raw = mm_deps.group(1).strip()
                if raw != "(none matched)":
                    deps = [x.strip() for x in raw.split(",") if x.strip()]
                    names = []
                    for d in deps:
                        if d.startswith("@"):
                            # scoped package: @scope/name@version
                            parts = d.rsplit("@", 1)
                            names.append(parts[0] if len(parts) == 2 else d)
                        elif "@" in d:
                            # unscoped package: name@version
                            names.append(d.rsplit("@", 1)[0])
                        else:
                            names.append(d)
                    pkg_rows[-1]["deps"] = uniq_keep_order(names)

    return {"mcp": mcp, "skills": skills, "packages": pkg_rows}


DOMAIN_KEYWORDS = {
    "frontend": ["frontend", "ui", "ux", "design", "landing", "web", "react", "component", "style"],
    "testing": ["test", "qa", "bug", "e2e", "playwright", "verify", "regression", "lint"],
    "deployment": ["deploy", "release", "ci", "cd", "vercel", "netlify", "cloudflare", "render"],
    "security": ["security", "vulnerability", "threat", "auth", "permission", "compliance"],
    "docs": ["doc", "documentation", "spec", "proposal", "report", "ppt", "slide"],
    "data": ["data", "sql", "dashboard", "analytics", "metric", "spreadsheet", "csv"],
    "automation": ["automation", "workflow", "agent", "mcp", "plugin", "skill", "integration"],
}


def detect_domains(task):
    lower = task.lower()
    found = []
    for d, kws in DOMAIN_KEYWORDS.items():
        if any(k in lower for k in kws):
            found.append(d)
    return found or ["automation"]


def select_skills(skills, domains):
    patterns = {
        "frontend": r"(frontend|theme|figma|webapp|playwright|screenshot)",
        "testing": r"(test|debug|review|verification|playwright|screenshot)",
        "deployment": r"(deploy|ci|gh-fix-ci|vercel|netlify|cloudflare|render)",
        "security": r"(security|threat)",
        "docs": r"(doc|docx|pptx|spreadsheet|notion|internal-comms)",
        "data": r"(spreadsheet|sentry|linear|openai-docs)",
        "automation": r"(skill-creator|mcp-builder|mcp-integration|dispatching-parallel-agents|using-superpowers|ax|cmx)",
    }
    picked = []
    for d in domains:
        pat = re.compile(patterns[d], re.IGNORECASE)
        for s in skills:
            if pat.search(s["name"]):
                picked.append(s["name"])
    return uniq_keep_order(picked)


def select_mcp(mcp, domains):
    names = uniq_keep_order([m["name"] for m in mcp])
    if "frontend" in domains and "chakra-ui" in names:
        names = ["chakra-ui"] + [x for x in names if x != "chakra-ui"]
    if "docs" in domains and "google-workspace" in names:
        names = ["google-workspace"] + [x for x in names if x != "google-workspace"]
    return names


def pick_project_libs(package_rows, project_root):
    project_root = str(Path(project_root).resolve())
    best = None
    for row in package_rows:
        r = row["root"]
        if project_root == r:
            return row["deps"]
        if project_root.startswith(r):
            if best is None or len(r) > len(best["root"]):
                best = row
    return best["deps"] if best else []


def join_caps(items, limit=8):
    if not items:
        return "(none)"
    trimmed = items[:limit]
    extra = len(items) - len(trimmed)
    if extra > 0:
        return ", ".join(trimmed) + f", +{extra} more"
    return ", ".join(trimmed)


def build_matrix(task, domains, mcp_names, skill_names, libs):
    matrix = []
    matrix.append(
        {
            "slice": "Capability Discovery",
            "caps": join_caps(["discover-all-capabilities.sh"] + mcp_names, 7),
            "why": "Build complete capability inventory before implementation.",
            "order": "1",
            "fallback": "Use saved manifest if live scan is unavailable.",
        }
    )
    matrix.append(
        {
            "slice": "Planning and Orchestration",
            "caps": join_caps([x for x in skill_names if x in {"ax", "cmx", "skill-creator", "writing-plans", "executing-plans"}], 8),
            "why": "Map capabilities to concrete task slices.",
            "order": "2",
            "fallback": "Create manual matrix from inventory sections.",
        }
    )
    impl_caps = []
    if "frontend" in domains:
        impl_caps += [x for x in skill_names if re.search(r"(frontend|theme|figma|webapp)", x, re.I)]
    if "deployment" in domains:
        impl_caps += [x for x in skill_names if re.search(r"(deploy|ci|vercel|netlify|cloudflare|render)", x, re.I)]
    if "docs" in domains:
        impl_caps += [x for x in skill_names if re.search(r"(doc|docx|pptx|notion|spreadsheet)", x, re.I)]
    impl_caps += libs
    matrix.append(
        {
            "slice": "Implementation",
            "caps": join_caps(uniq_keep_order(impl_caps), 10),
            "why": "Execute using domain-matched skills and dependency stacks.",
            "order": "3",
            "fallback": "Use closest existing framework stack in project dependencies.",
        }
    )
    verify_caps = [x for x in skill_names if re.search(r"(test|debug|review|verification|playwright|screenshot)", x, re.I)]
    matrix.append(
        {
            "slice": "Verification",
            "caps": join_caps(uniq_keep_order(verify_caps), 10),
            "why": "Validate behavior, quality, and regressions.",
            "order": "4",
            "fallback": "Run project-native tests and manual checks.",
        }
    )
    handoff_caps = [x for x in skill_names if re.search(r"(internal-comms|doc|notion|gh-address-comments|linear)", x, re.I)]
    matrix.append(
        {
            "slice": "Delivery and Handoff",
            "caps": join_caps(uniq_keep_order(handoff_caps), 10),
            "why": "Package outputs, communicate changes, and close loop.",
            "order": "5",
            "fallback": "Provide concise changelog plus verification evidence.",
        }
    )
    return matrix


def render_markdown(task, domains, parsed, libs, matrix):
    out = []
    out.append("# Capability-to-Task Matrix")
    out.append("")
    out.append(f"**Task**: {task}")
    out.append("")
    out.append(f"**Detected domains**: {', '.join(domains)}")
    out.append("")
    out.append("## Inventory Summary")
    out.append("")
    out.append(f"- MCP servers: {len(parsed['mcp'])}")
    out.append(f"- Skills: {len(parsed['skills'])}")
    out.append(f"- Package capability roots: {len(parsed['packages'])}")
    out.append(f"- Project library stack size: {len(libs)}")
    out.append("")
    out.append("## Matrix")
    out.append("")
    out.append("| Task Slice | Capability Set | Why | Order | Fallback |")
    out.append("| --- | --- | --- | --- | --- |")
    for row in matrix:
        out.append(
            f"| {row['slice']} | {row['caps']} | {row['why']} | {row['order']} | {row['fallback']} |"
        )
    out.append("")
    out.append("## Invocation Order")
    out.append("")
    out.append("1. Run capability discovery and confirm inventory.")
    out.append("2. Finalize matrix row ownership and sequence.")
    out.append("3. Execute implementation with mapped capabilities.")
    out.append("4. Verify and iterate.")
    out.append("5. Deliver with evidence and fallback notes.")
    out.append("")
    return "\n".join(out)


def main():
    parser = argparse.ArgumentParser(description="Generate capability-to-task matrix markdown.")
    parser.add_argument("--manifest", required=True, help="Path to capability manifest markdown.")
    parser.add_argument("--project", required=True, help="Project root path.")
    parser.add_argument("--task", required=True, help="Task statement.")
    parser.add_argument("--out", required=True, help="Output markdown path.")
    args = parser.parse_args()

    manifest_text = Path(args.manifest).read_text()
    parsed = parse_manifest(manifest_text)
    domains = detect_domains(args.task)
    all_skill_names = uniq_keep_order([s["name"] for s in parsed["skills"]])
    skill_names = select_skills(parsed["skills"], domains)
    for core in ["ax", "cmx", "skill-creator", "writing-plans", "executing-plans", "using-superpowers"]:
        if core in all_skill_names:
            skill_names = uniq_keep_order([core] + skill_names)
    mcp_names = select_mcp(parsed["mcp"], domains)
    libs = pick_project_libs(parsed["packages"], args.project)
    matrix = build_matrix(args.task, domains, mcp_names, skill_names, libs)
    md = render_markdown(args.task, domains, parsed, libs, matrix)
    Path(args.out).write_text(md)


if __name__ == "__main__":
    main()
