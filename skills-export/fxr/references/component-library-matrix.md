# Component Library Matrix

Use this matrix to avoid random library mixing and keep a coherent system.

## 1. Default Ownership

1. `@mui/material`: complex dashboards, data density layouts, admin navigation.
2. `@mui/joy`: brand-forward, editorial, or marketing-heavy sections where visual personality matters.
3. `antd`: enterprise forms, validation-heavy workflows, tables with advanced filtering.
4. `@chakra-ui/react`: fast composition of responsive layouts and reusable UI primitives.
5. `@base-ui/react`: headless primitives where full custom styling and behavior control are required.
6. `@fluentui/react-components`: Microsoft-style productivity workflows and collaborative UI patterns.
7. `@fluentui/web-components`: standards-based web component scenarios crossing framework boundaries.

## 2. Shared Integration Strategy

1. Keep one source of truth for tokens: CSS variables + central token map.
2. Build per-library theme adapters that read from the same token source.
3. Wrap third-party components with project-level adapters when style or behavior must be normalized.
4. Enforce state consistency (`hover`, `focus`, `active`, `disabled`, `loading`, `error`, `success`) across all libraries.

## 3. Conflict Controls

1. Check style engine consistency before implementation.
2. If MUI is used with Emotion, avoid accidental parallel style systems in the same subtree unless required.
3. If using `styled-components` with MUI, verify styled engine configuration and SSR strategy.
4. Avoid importing similar components from multiple libraries on the same surface unless there is a clear reason.

## 4. Practical Rules

1. Keep one "primary" UI library per page or feature area.
2. Use secondary libraries only for clear capability gaps.
3. Document every exception in the delivery matrix.
4. When users request "use all installed libraries," satisfy it with explicit scoped ownership, not arbitrary mixing.

