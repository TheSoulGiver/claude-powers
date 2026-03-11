# Screenshot Iteration Loop

Use this loop to verify real visual output instead of guessing from code.

## 1. Baseline Capture

1. List target routes and critical conversion paths.
2. Define fixed viewports for comparison:
   - Desktop: `1440x900`
   - Mobile: `390x844`
3. Capture baseline screenshots for each route and viewport before edits.

## 2. Iteration Cycle

For each meaningful UI batch:

1. Capture current screenshot.
2. Compare with previous screenshot at the same route and viewport.
3. Annotate changes:
   - visual hierarchy
   - readability
   - interaction clarity
   - conversion friction
   - brand consistency
4. Apply code updates.
5. Re-capture and re-check.

## 3. No-Completion Conditions

Do not mark work done when any condition is true:

1. No screenshot evidence exists.
2. Before/after views use different routes or viewport sizes.
3. Core breakpoints are missing.
4. Major visual inconsistencies remain unresolved.

## 4. Suggested Acceptance Checks

1. CTA visibility and intent clarity improved.
2. Information density is controlled and scannable.
3. Interactive states are obvious and consistent.
4. Motion supports comprehension and does not distract.
5. Typography, spacing, and color feel unified across pages.

