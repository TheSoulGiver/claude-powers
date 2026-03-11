# Capability-to-Task Matrix

**Task**: Use all MCP and all skills to build a cross-stack execution matrix

**Detected domains**: frontend, automation

## Inventory Summary

- MCP servers: 6
- Skills: 87
- Package capability roots: 15
- Project library stack size: 19

## Matrix

| Task Slice | Capability Set | Why | Order | Fallback |
| --- | --- | --- | --- | --- |
| Capability Discovery | discover-all-capabilities.sh, chakra-ui, openclaw-bridge, google-workspace | Build complete capability inventory before implementation. | 1 | Use saved manifest if live scan is unavailable. |
| Planning and Orchestration | executing-plans, writing-plans, skill-creator, cmx, ax | Map capabilities to concrete task slices. | 2 | Create manual matrix from inventory sections. |
| Implementation | frontend-design, theme-factory, webapp-testing, "figma-implement-design", figma, @base-ui/react, @chakra-ui/react, @emotion/react, @emotion/styled, @fluentui/react-components, +14 more | Execute using domain-matched skills and dependency stacks. | 3 | Use closest existing framework stack in project dependencies. |
| Verification | webapp-testing, "playwright", "screenshot" | Validate behavior, quality, and regressions. | 4 | Run project-native tests and manual checks. |
| Delivery and Handoff | (none) | Package outputs, communicate changes, and close loop. | 5 | Provide concise changelog plus verification evidence. |

## Invocation Order

1. Run capability discovery and confirm inventory.
2. Finalize matrix row ownership and sequence.
3. Execute implementation with mapped capabilities.
4. Verify and iterate.
5. Deliver with evidence and fallback notes.
