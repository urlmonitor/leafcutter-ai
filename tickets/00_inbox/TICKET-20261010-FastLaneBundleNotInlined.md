---
title: "The fast lane halts when its bundle agent returns a pointer instead of a 21 KB bundle"
status: todo
components:
  - build_orchestration
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: high
roadmap_phase: phase_1
change_target: infrastructure
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# The fast lane halts when its bundle agent returns a pointer instead of a 21 KB bundle

## Actor / Goal
In order for a fast-lane run not to halt on a sound context bundle, the lane must get the bundle without asking an agent to copy ~20 KB of text into a JSON field.

## Context
- **Recurrence of KI-BO-019** (`docs/known-issues/build-orchestration/resolved/resolved-blocker-ki-bo-019.md`), closed 2026-09-23 without a live run and with the instruction to reopen it on a new symptom.
- **New symptom, 2026-10-10** (`/fast-lane-build DK-600a-3`, run `wf_92b45058-872`): `assemble-bundle` exited 0 with 21,325 bytes, which is within the ~20 KB the closure relied on. The bundle agent (python-coder) still returned `obtained: false` with "the full verbatim text was not placed in the bundle field; refusing to return a truncated or fabricated bundle. Output is at the scratchpad out.txt". The lane halted at `context-bundle` and released the AC. A second run passed this step, so the failure is nondeterministic.
- The cut to three layers did not remove the transport risk; it only made it less likely.

## Scope
1. Take KI-BO-019's first fix direction: `assemble-bundle` returns a small verdict (`ok`, `bytes`, marker present, path), the lane gates on that verdict, and the lane or its next phase reads the file itself.
2. Keep the fail-closed behaviour for a missing marker or a failed assembly.
3. Reopen or supersede KI-BO-019 with this occurrence.

## Out of Scope
- Changing the bundle's layers.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
