---
title: "The fast-lane how-tos describe a lane without review, PR or producibility refusal"
status: todo
components:
  - build_orchestration
created: 2026-10-10
last_updated: 2026-10-10
depends_on: []
priority: medium
roadmap_phase: phase_1
change_target: documentation
risk_surface: internal
requires_diagram: false
requires_adr: false
agents:
  how-to-author: needed
  documentation-verifier: needed
  commit: needed
  pull-request: needed
---

# The fast-lane how-tos describe a lane without review, PR or producibility refusal

## Actor / Goal
In order for a person or the kernel to choose a build path from the docs, the fast-lane how-tos must match what `fast-lane-ship.js` does.

## Context
- **Found:** 2026-10-10, the DK-600 build-path decision (`dec-ea83c3989d1b7199`). A first kernel ranking rested on these docs and was wrong; an independent review read the code.
- **Stale statements:**
  - `docs/how-to/fast-lane-build.md` (around L26, L394-396, L450-451): "two dispatches", "the workflow itself does not commit", and "PR creation / Review agents: Not included". The lane makes 11 agent dispatches on the happy path, runs a blocking `pr-reviewer` at Phase 4.5 (since #485), commits and opens the PR (`templates/workflows-js/fast-lane-ship.js`).
  - `docs/how-to/choose-build-path.md` (2026-07-21) does not mention the producibility refusal (#570): a build set with a `test_required: false` AC or an `assigned_agent` outside {python-coder, test-writer} is refused up front (`scripts/build_orchestration/_fl_producibility.py`). It also does not say that `choose_lane` is advisory and called by no entry point.
  - `docs/known-issues/build-orchestration/open-high-ki-bo-013.md` describes the old mechanism (jams at commit); the outcome now is an up-front refusal.
- `docs/architecture/diagrams/c3-fast-lane-build-loop-sequence.md` and `c2-fast-lane-build-path-components.md` are already correct and can be linked.

## Scope
1. Correct the three statements in `fast-lane-build.md` and link the c2/c3 diagrams.
2. Add the producibility refusal and the advisory status of `choose_lane` to `choose-build-path.md`.
3. Update KI-BO-013's symptom to the current mechanism.

## Out of Scope
- Adding a documentation phase to the fast lane (ADR-035 defers it).

## Sign-offs

- [ ] how-to-author
- [ ] documentation-verifier
- [ ] commit
- [ ] pull-request

## Comments
