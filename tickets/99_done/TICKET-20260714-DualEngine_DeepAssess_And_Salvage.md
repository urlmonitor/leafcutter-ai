---
title: "DualEngine: deep-assess current state, then merge-or-salvage the workflow engine"
status: done
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

### 2026-07-14 — deep-assessment (status: ok)

**Verdict: NEITHER MERGE NOR SALVAGE. The epic is already fully merged and live on
`origin/main`. This ticket's premise was stale — exactly the CQG-style false
"known-broken" flag it warned about.**

**Key structural finding:** the epic branch `origin/EPIC-DualEngineWorkflowSupport`
**no longer exists** (deleted at squash-merge). There is no branch to merge or salvage
from. PR #198 (`bf73f9a6`) was a **squash-merge of the entire branch** — all 13 tickets
(01–13, including remediation tickets 08–13), not just 01–04. `git show bf73f9a6 --stat`
shows +7907/-2866 across `build-feature.js` (+413 net-new), `plan-feature.js`,
`finalize-feature.js`, `build-epic.js`, `build-ticket.js`, `build_phases.py`,
command templates, ADR-030, the authoring contract, and the full dual-engine test suite.

**AC-1 — per-artifact state on `main` (evidence: file content on `origin/main`):**
- `build-feature.js` — present & correct (pure-literal `meta`; Phase-0 worktree establish;
  `.git`-file worktree detection).
- `plan-feature.js` / `finalize-feature.js` / `build-epic.js` / `build-ticket.js` —
  present & correct (all rewritten to E2 canonical form).
- default-engine flip — present: `config/skills_config.default.json` →
  `workflows.engine: "auto"` (resolves to E2, the engine that runs here).
- `build_phases.py` variant transform — present & correct (E2-only; E1 wrap removed).

**AC-2 — the 6 HIGH defects, all ALREADY-FIXED on `main` (evidence: content):**
1. plan-feature empty input → command passes `{ userInput: $ARGUMENTS }`, script reads
   `args.userInput`. Fixed.
2. `build-feature.js` missing/orphaned → exists (+413) and dispatches. Fixed.
3. E1-wrap unloadable module → E1 removed; `_emit_workflow_variant("e1")` raises
   `ValueError` (ticket 09). Fixed.
4. `build-epic` spread-form `parallel()` → array-of-thunks form
   `parallel(chunk.map((t) => async () => …))`. Fixed.
5. plan-feature no-main-commit guard fail-open → now explicitly **fail-CLOSED**, aborts
   on any unconfirmed branch (AC BO-1500c-3). Fixed.
6. real-engine defects (meta-not-literal / no-worktree / reads-main-clone, tickets 11–13)
   → all fixed in `build-feature.js`. Fixed.

**AC-3 — real-engine behavioral spot-check (observed 2026-07-14):** `/build-feature`
against this very ticket path ran as a **real E2 workflow** (Workflow tool, fresh
process): dispatched `status-checker` + `worktree-agent` (2 real agents), then aborted
**loudly** on the missing ticket file with "will NOT fall back to driving phase agents
against the main clone." That is the epic's exact intended behavior — no silent no-op,
no LLM fallback. **PASS.**

**AC-4 — recommendation:** neither MERGE nor SALVAGE-FRESH applies (no branch exists;
nothing unmerged). The correct action is to **close this ticket as obsolete/superseded
by PR #198** and **archive `EPIC-DualEngineWorkflowSupport/` to `99_done/`** (the only
residual — the epic folder was never archived despite all 13 sub-tickets being
`status: done`). Both done in this commit.

**AC-5 — `main` not regressed:** nothing was executed against the engine; this is a
tickets-only change. Required gates (ruff + schema-diff) are unaffected.

The stale `origin/EPIC-DualEngineWorkflowSupport` branch is already gone, so the
"delete the stale branch" implementation task is moot.

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
