---
name: fxr
description: Integrated frontend refactor skill. Use for full UI/UX overhauls, design-system rebuilds, cross-page style unification, conversion optimization, and screenshot-driven iteration. Trigger when user asks for major frontend redesign or types "fxr"/"$fxr".
---

# FXR

Scan local frontend capabilities, orchestrate them, and deliver screenshot-proven refactors.

## Mandatory Startup Checklist

1. Locate the project root and identify framework/build tools before editing.
2. If `~/Desktop/masters.md` exists, read it and extract only roles relevant to the current page set.
3. Run `scripts/discover-frontend-capabilities.sh <project-root>` to inventory MCP, skills, and UI libraries.
4. Build a capability-to-task orchestration matrix before coding.
5. Run `scripts/check-ui-stack.sh <project-root>` to audit declared and installed UI dependencies.
6. Load references only as needed:
   - `references/component-library-matrix.md`
   - `references/integration-orchestration.md`
   - `references/screenshot-iteration-loop.md`

If any item is unavailable, continue with the best equivalent approach and explicitly note the fallback.

## Non-Negotiable Rules

1. Never paste JSON, TSX, YAML, or markdown snippets directly into shell as commands.
2. Edit project files directly when configuring code or metadata.
3. Capture baseline screenshots before major UI changes.
4. Re-capture and compare after each meaningful iteration.
5. Use all relevant local capabilities discovered in startup scan; do not skip applicable MCP/skills/libraries without reason.
6. Do not claim completion without visual evidence and quality metrics.

## Execution Workflow

### 1. Baseline Discovery

1. Inventory all relevant routes/pages and core conversion paths.
2. Capture baseline screenshots on desktop and mobile viewports.
3. Prioritize UI debt: consistency, usability, conversion friction, accessibility.

### 2. Rebuild the Design System

1. Define unified design tokens (color, typography, spacing, radius, shadow, motion).
2. Build or update a theme layer and component adapters before page-level refactors.
3. Standardize states: default, hover, focus, active, disabled, loading, error, success.

### 3. Multi-Library Responsibility Split

Use `references/component-library-matrix.md` to assign clear ownership across:
- `@mui/material`, `@mui/joy`, `@mui/icons-material`
- `antd`
- `@chakra-ui/react`
- `@base-ui/react`
- `@fluentui/react-components`, `@fluentui/web-components`

When users request "use all installed frontend stacks," include every discovered frontend library in the matrix with concrete page/component ownership and non-overlapping roles.

### 4. Iterative Refactor Loop

Run the full loop from `references/screenshot-iteration-loop.md`:
1. Capture
2. Compare
3. Diagnose
4. Modify
5. Re-capture

Repeat until all acceptance gates pass.

### 5. Capability-Orchestrated Delivery

Use `references/integration-orchestration.md` to:
1. map tasks to MCP and skills
2. map pages to component libraries
3. define invocation order and fallback path
4. keep one unified visual language despite multi-stack execution

### 6. Verification and Handoff

1. Verify responsive behavior across critical breakpoints.
2. Verify accessibility and keyboard navigation.
3. Verify performance and runtime stability.
4. Deliver before/after screenshots, component/library matrix, and measurable improvements.

## Quality Gates (Default Targets)

1. Lighthouse: Performance >= 90, Accessibility >= 95, Best Practices >= 95, SEO >= 90.
2. Core Web Vitals: LCP < 2.5s, CLS < 0.1, INP < 200ms.
3. WCAG 2.2 AA checks for keyboard access, contrast, semantic structure, and focus visibility.
4. No visual style fragmentation across pages after library integration.

If constraints prevent exact targets, report current values, blockers, and a concrete follow-up plan.

## Required Output Format

1. Capability inventory (`MCP + skills + libraries`) and orchestration matrix.
2. Baseline findings (with screenshots).
3. Design-system/token changes.
4. Library usage matrix (page -> component -> library -> reason).
5. Iteration logs (before/after screenshots + what changed + why).
6. Final verification summary (performance, accessibility, responsive, conversion-path quality).
