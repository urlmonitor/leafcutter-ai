---
title: "DualEngine: deep-assess current state, then merge-or-salvage the workflow engine"
status: todo
components:
  - build_orchestration
  - supervisor_system
  - infrastructure
created: 2026-07-14
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
tags:
  - handoff
  - salvage
  - dual-engine
---

# DualEngine: deep-assess current state, then merge-or-salvage the workflow engine

## Actor / Goal

In order to finish EPIC-DualEngineWorkflowSupport safely, we need an agent to
**independently verify the current state** of the workflow engine (on `main`
vs. the epic branch) and then execute the correct path — a clean merge if the
branch is sound, or a fresh salvage if it is not — so the deterministic
workflow engine actually ships without regressing `main`.

## Context

EPIC-DualEngineWorkflowSupport (folder
`tickets/00_inbox/epics/EPIC-DualEngineWorkflowSupport/`) has all 13 sub-tickets
marked `status: done`, but its implementation is **not** fully on `main`.

Point-in-time findings (2026-07-14 — **treat as leads to re-verify, NOT as
fact**; a sibling epic in this same review, ComputedQualityGates, carried an
identical "known-broken" flag that turned out to be stale):

- **Only the foundation landed on `main`** via PR #198 (tickets 01–04):
  `workflows.enabled` / `workflows.engine` config keys, a zero-dispatch CI
  guard, the ADR, and `_emit_workflow_variant`.
- **The actual E2 port is unmerged** — the port of
  `plan-feature.js` / `finalize-feature.js` / `build-epic.js` / `build-ticket.js`,
  the default-engine flip, `build-feature.js` command wiring, and remediation
  work sit on `origin/EPIC-DualEngineWorkflowSupport` (~45 commits ahead).
- That branch was flagged with **6 HIGH defects** in a prior review and
  "do NOT merge as-is" (see memory `project_dualengine_epic_broken_unmerged`).
- Quick check on `main` 2026-07-14: the workflow engine is **not the default**
  (no `engine` set in `config/skills_config.json`); `templates/workflows-js/`
  and the `check_workflow_meta` gate exist.

The branch is also **stale relative to `main`** (main has advanced far since the
last merge from main into the branch), so a naive `git merge` will be a mess —
see memory `feedback_pr_salvage_fresh_ids` (stale-PR rot: main drifts the
branch's files and re-uses its AC-ID block, causing DIRTY merges and silent
duplicate-ID store corruption that schema-diff will NOT catch).

## Acceptance Criteria

- [ ] AC-1: A written assessment states, per major artifact
  (`plan-feature.js`, `finalize-feature.js`, `build-epic.js`, `build-ticket.js`,
  `build-feature.js` command wiring, default-engine flip), whether it is present
  and correct on `main`, present-but-broken, or absent — each backed by concrete
  evidence (file content on `main`, `git log`, or a behavioral run), not by
  trusting prior memory/audit notes.
- [ ] AC-2: Each of the 6 previously-flagged HIGH defects is re-checked against
  current `main` + branch and classified as still-present / already-fixed /
  not-reproducible, with evidence.
- [ ] AC-3: A behavioral spot-check runs at least one real workflow end-to-end
  through the engine path (real engine, real inputs, fresh process — per
  `feedback_behavioral_spotcheck_real_store`) and its actual observed output is
  recorded (pass or fail).
- [ ] AC-4: A recommendation is produced — **MERGE** (branch is sound; give the
  exact rebase/merge + verification steps) or **SALVAGE-FRESH** (re-author the
  correct subset under pre-assigned free AC-IDs via `/plan-feature` in an
  isolated worktree, per `feedback_pr_salvage_fresh_ids`) — with the concrete
  next steps for whichever path is chosen.
- [ ] AC-5: If the chosen path is executed, `main` is not regressed: required
  gates (ruff + schema-diff) stay green and the pre-existing non-required pytest
  state is unchanged.

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Bootstrap a fresh worktree off `origin/main` (do NOT use local `main`;
  see `project_single_ticket_stale_local_main`).
- [ ] Diff `origin/main` vs `origin/EPIC-DualEngineWorkflowSupport` by **content**
  (not just `git log` — squash merges make the ahead-list misleading; confirm
  with file-content checks, as the CQG assessment showed).
- [ ] Re-verify the 6 HIGH defects and the E2-port presence per AC-1/AC-2.
- [ ] Run the real-engine behavioral spot-check (AC-3).
- [ ] Write the assessment + recommendation (AC-4).
- [ ] Execute the chosen path if authorized, keeping `main` green (AC-5).
- [ ] When done, delete the stale `origin/EPIC-DualEngineWorkflowSupport` branch
  if superseded.

## Risk & Safety

- Touches money? No.
- Touches data? The AC store — a bad merge can silently create duplicate AC IDs
  that schema-diff will not catch. Verify store integrity after any merge/salvage.
- Reversibility? Work in an isolated worktree; land via PR only. Do not merge the
  epic branch directly without the assessment above.

## Related

- Epic: `tickets/00_inbox/epics/EPIC-DualEngineWorkflowSupport/`
- Branch: `origin/EPIC-DualEngineWorkflowSupport`
- Memory: `project_dualengine_epic_broken_unmerged`, `feedback_pr_salvage_fresh_ids`,
  `feedback_behavioral_spotcheck_real_store`, `project_toolchain_workflow_runner_dead`
