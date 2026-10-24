---
title: "EPIC: Harden the BO-4300 workspace maker"
type: epic
epic_name: EPIC-WorkspaceMakerHardening
created: '2026-10-22'
last_updated: '2026-10-22'
status: todo
components:
  - worktree_manager
  - build_orchestration
  - testing_quality
  - commit_guardian
depends_on: []
change_target: code
risk_surface: safety
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - BO-4300
  - bo4300-hardening
---
# EPIC-WorkspaceMakerHardening

## Goal

Harden the merged BO-4300 workspace maker (`templates/scripts/worktree*.py`, `workspace_root.py`,
deployed to `<install>/scripts/`) so that it does what the BO-4300 ACs already promise. The defects come
from HANDOVER-v2 (2026-10-22, written against `fb09c867d` and spot-checked on main): M2-M17, N1-N8 and
the port notes P8-P10. M1 (the conflict with main) is already resolved, and M18 (the informational mypy
job) is deliberately not grouped. It follows H07 and H08.

Every item was checked against the BO-4300 AC store by the business-analyst. The verdict was either
"covered by an existing clause" or "needs an amendment or a new AC". The approved amendments (A1-A14) are
applied to `docs/acceptance-criteria/` separately; these tickets do not edit the AC store, except where
ac-fulfillment-gate auto-fixes `work_status` / `implemented_by` / `covered_by`.

Build mode (user decision 2026-10-22): phases are dispatched directly in this session, one lane per
ticket. There is no `/build-feature` workflow run.

## Tickets

| # | File | Title | Items | ACs | Wave | Depends On | Status |
|---|------|-------|-------|-----|------|------------|--------|
| 01 | [01_TICKET-20261022-maker-never-waits-for-input.md](./01_TICKET-20261022-maker-never-waits-for-input.md) | The workspace maker never waits for input | M3, N5 (never-prompts) | c-2, a-1, e-2, f-3 | 1 | -- | `[ ]` |
| 02 | [02_TICKET-20261022-workflows-run-maker-by-absolute-path.md](./02_TICKET-20261022-workflows-run-maker-by-absolute-path.md) | Workflows run the maker by its absolute path and stop when a shell step fails | M13, M16, M5 (caller re-check) | a-1-ia, a-1-ib | 1 | -- | `[ ]` |
| 03 | [03_TICKET-20261022-proof-harness-bounded-deployed-maker.md](./03_TICKET-20261022-proof-harness-bounded-deployed-maker.md) | The proof harness runs the deployed maker in a bounded environment, proves the marker survives the real build, runs the family in CI and records timings | M15, M14 (A11), N3 (A12), N4 (A13) | c-2 (test ITs), f-4, f-4-i, a-1 IT9/IT12 | 1 | -- | `[ ]` |
| 04 | [04_TICKET-20261022-clearing-stays-inside-project.md](./04_TICKET-20261022-clearing-stays-inside-project.md) | Clearing stays inside the project, keeps git's text out of the answer, and fails before deleting | M4 (remove), M5 (remove, A6/A7), M9a, M17 | e-2, e-2-i, e-2-iii, e-3, e-3-ii, c-2 | 1 | -- | `[ ]` |
| 05 | [05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md](./05_TICKET-20261022-ensure-clones-main-checkout-contract-shape.md) | Ensure clones the main checkout and answers in the contract's exact shape | M2 (ensure, A1), M4 (ensure, ticket record), M9c/N1, M9d (A2, A10), N5 (no git text) | a-1, d-4, c-2, BO-400e-3-ix | 2 | 01 | `[ ]` |
| 06 | [06_TICKET-20261022-work-identity-safe-slugs-canonical-first.md](./06_TICKET-20261022-work-identity-safe-slugs-canonical-first.md) | Work identities: safe slugs, canonical spelling first, one identity per line | M11 (A5), M10 (A4, naming table), M17 (discard_new_clone) | a-2 | 2 | 01, 04 | `[ ]` |
| 07 | [07_TICKET-20261022-read-only-verbs-refuse-and-answer-contract-shape.md](./07_TICKET-20261022-read-only-verbs-refuse-and-answer-contract-shape.md) | Read-only verbs: verify refuses, and locate, verify and list answer in the contract's shape | M5 (verify, A3), M7, M8, N8, M9b/N2 (A2 item 6), M12 | c-1, c-2, b-4, e-1, a-2 | 3 | 05, 06 | `[ ]` |
| 08 | [08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md](./08_TICKET-20261022-cut-over-canonical-deferred-readiness-lossless.md) | The cut-over clones the main checkout, uses the canonical identity, defers readiness and loses nothing silently | M2 (migrate), M4 (migrate), M6/N6 (A8), M10 (cut-over, A4), M17, N7 (A9b), P9 (A9) | f-3, f-3-iii, f-3-iv, a-2 | 4 | 04, 06, 07 | `[ ]` |
| 09 | [09_TICKET-20261022-self-heal-ordering-guard-fails-closed.md](./09_TICKET-20261022-self-heal-ordering-guard-fails-closed.md) | The self-healing hook's ordering guard accepts only stage canaries before it and fails closed otherwise | A14 | BO-1700c-1-iii | any (1) | -- | `[ ]` |

AC ids without a prefix are `BO-4300<id>`. The ACs new in this epic (BO-4300e-2-iii, e-3-ii, f-3-iii,
f-3-iv) and the amended clauses are written to the AC store by a separate pass. Each ticket's
`ac_traceability` resolves only once those YAML files exist.

## Waves and dependencies

```
wave 1:  01   02   03   04   09          (disjoint files; run in parallel lanes)
wave 2:  05 <- 01                        (worktree_git.py after 01)
         06 <- 01, 04                    (worktree_identity.py after 01; shared delete helper from 04)
wave 3:  07 <- 05, 06                    (worktree.py after 05; identity resolve after 06)
wave 4:  08 <- 04, 06, 07                (shared delete/status helpers from 04; canonical identity from 06;
                                          verify/readiness shape from 07)
```

## File-ownership rule

Within a wave, each file has exactly one owning ticket. A ticket edits only its `files_touched`. If a
ticket finds that it needs a file another ticket owns in the same wave, it stops and reports the need.
It does not make the edit. Files that are owned in more than one wave are handed on in wave order:

| File | Owner by wave |
|------|---------------|
| templates/scripts/worktree_git.py | 01 (w1) -> 05 (w2) |
| templates/scripts/worktree_identity.py | 01 (w1, `_show_bytes` only) -> 06 (w2) |
| templates/scripts/worktree.py | 05 (w2, ensure path) -> 07 (w3, `cmd_verify`) -> 08 (w4, only the `completed` path for brought-over workspaces, if needed) |
| templates/scripts/worktree_readiness.py | 07 (w3) -> 08 (w4, only if A8's completion needs it) |
| templates/scripts/worktree_remove.py | 04 (w1) only. 06 and 08 import its shared delete and status helpers but do not edit them. |
| templates/scripts/worktree_answer.py | 05 (w2) only. Ticket 04 must NOT edit it. |
| docs/reference/workspace-maker-answer.md | 07 (w3) only |

Shared, read-only for everyone: `unit_tests/build_orchestration/_workspace_maker_fixtures.py`,
`_workspace_maker_builders.py` and `_workspace_maker_build_helpers.py`. Ticket 03 owns them in wave 1, and
later tickets use them as they are. Every new maker test resolves the DEPLOYED maker through
`deployed_maker_path()`, runs it with `run_maker`, and builds its fixture with `make_project` /
`legacy_worktree` / `link_checkout`. No test spawns `scripts/build.py` beyond the one shared deployed layout.

## Decisions taken on 2026-10-22 (user, with every recommended option chosen)

- A1, A2, A3, A5, A6, A7, A9, A10, A12 and A14 are approved as drafted in DECISIONS.md.
  - A2 item 6 takes option (i): on locate and verify, `workspace_action` is `located`, `line_of_work` is
    `existing`, `created` is false, `fetch` is `skipped`, and `origin_main_commit` is the last-fetched
    origin/main.
  - A3: verify never refuses on `base_is_fresh` or `tree_clean`.
  - A5: single dots are allowed in slugs.
  - A9: a staged change is either carried over with the index kept, or listed for a decision.
- A4 (M10), option A: drop the alias `ticket <- feature/<slug>`. `feature/<slug>` always resolves to kind
  feature.
- A8 (M6/N6), option 1: defer readiness. A brought-over workspace's marker state is `creating`, and its
  `brought_over` entry carries a `next` ensure hint.
- A9b (N7), option R: delete the ignored content and report it in `ignored_removed`. The preview lists the
  same paths.
- A11 (M14), option 2: a dedicated CI job runs the deployed-maker tests on PRs that touch the maker's files.
- A13 (N4), option 2: record the timings, and fail only above 2x the budget.
- BO-400e-3-ix scenario 2 is kept, reworded for existing legacy `feature/` lines that carry a
  built-for-ticket record.
- `.leafcutter/rescue/` is shipped behaviour (`templates/scripts/worktree_ensure_state.py`), so A12 applies.

## Out of scope

- M18 (mypy).
- The doc and ADR housekeeping in HANDOVER-v2: the ADR-070 history, the ADR-018 amendment move, and the
  status mismatches.
- The v1 docs fold-in (D1-D3).
- The finalize-ordering anomaly A10 notes: the built-for-ticket record lives in the workspace clone's
  config and is gone after removal.
