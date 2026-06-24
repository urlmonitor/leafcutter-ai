---
title: "EPIC: Harden the finalize-feature flow (workflow meta, dead fallback, reconciliation, env robustness)"
type: epic
status: in_progress
components:
  - build_pipeline
  - supervisor_system
  - ticket_lifecycle
created: 2026-06-24
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
---

# EPIC: Harden the finalize-feature flow

## Goal

In order to make `/finalize-feature` reliably executable end-to-end on every
supported Claude Code install, we need to fix the two bugs that currently leave
it with no working execution path, retire its non-functional fallback, close
the surrounding environmental and process gaps, and close the AC-first build
loop by marking shipped ACs done — so that finishing a feature is a one-command
operation again instead of a manual `git -C` drive, and the AC store stays
truthful after every merge.

## Context

During a manual single-ticket finalize (branch `feature/acschemahookstagedscope`,
PR #152, merged 2026-06-24) the `/finalize-feature` command could not run by
either of its documented paths, and several latent defects surfaced — including
one (folder reconciliation) that the run itself reproduced live. Three parallel
analysis agents diagnosed root causes and proper fixes; this epic captures them.

### The two primary breakages (no working path today)

1. **JS workflow rejected at parse time.** The `Workflow` tool requires the
   `export const meta = {...}` block to be a **pure literal**. `finalize-feature.js`
   builds `meta.description` and several `meta.phases` entries with string
   concatenation (`"..." + "..."` → `BinaryExpression`), so the tool rejects it
   with `meta must be a pure literal: non-literal node type in meta: BinaryExpression`
   before `run()` ever executes. **5 of 6 scripts in `templates/workflows-js/`
   share this defect** (only `quick-fix.js` is clean) — the other four are latent,
   failing the instant they are invoked via the Workflow tool. Nothing in the repo
   validates this: `build_phases.py` byte-copies the scripts without parsing `meta`.

2. **The agent fallback is dead code on every version.** The slash command offers
   the `finalize-feature` LLM agent as a fallback "for older Claude Code versions",
   but that agent is a `tier: supervisor` that dispatches `pull-request`,
   `status-checker`, `worktree-agent`, `test-runner`, `test-failure-triage`. When
   invoked it runs at depth 1, so its dispatches are depth 2 — which Claude Code
   **silently drops** (ADR-006). The depth-1 limit is a hard platform constraint
   with no version gate, so the fallback never worked on any version; worse, it
   fails silently (reports success while nothing merges). The ADR-006 deprecation
   that was completed for `epic-supervisor` was never done for `finalize-feature`.

### Surrounding robustness gaps (surfaced during the manual run)

3. **Folder reconciliation cannot reach a PR-only `main` (P0, reproduced live).**
   Step 6c does `git mv` (inbox→`99_done`) + `git commit` on local `main`, but
   never pushes — and `main` is PR-only (ruff branch protection rejects direct
   push). The reconciliation commit stays local-only, diverges from origin, and is
   dropped on the next pull. The EPIC-MoveOnMainOnly tickets already show duplicate
   inbox+done copies on origin from this exact mechanism. Fix direction: treat
   frontmatter `status:` as the sole source of truth and stop physical moves on
   main (the prioritizer/archive-check stack already ignores folder position).

4. **`gh` EMU-account pre-flight missing (P0).** Every `gh` call in the workflow
   assumes the active account can operate on the repo, but the default-active
   account here is the EMU `henzeh_roche`, which silently blocks PR create/merge.
   The workflow does no `gh auth switch --user urlmonitor` + `gh auth status`
   verification and has no REST-API fallback.

5. **CWD-trusting git detection (P1).** `finalize-feature.js` pre-flight and
   `setup_ticket_worktree.py::_git_toplevel()` resolve the repo via `git rev-parse`
   in the process CWD, which breaks in the self-hosting layout where the git root
   is `leafcutter-ai/` but the session CWD is its untracked parent `leafcutter/`
   (ADR-001). They should anchor on an explicit repo path / `git -C`.

6. **Poetry-only bootstrap (P1).** `setup_ticket_worktree.py::_bootstrap()` hard-codes
   `poetry install --no-root` with `check=True`, but this repo has no `pyproject.toml`
   (it uses `requirements-dev.txt`). The call always fails, aborting before `build.py`
   runs and leaving a half-bootstrapped worktree. Also a portability bug for
   pip-based adopters. Detect the dependency manager; make the step non-fatal.

7. **Dead Step 6a auto-ticketing (P1).** `create-ticket` was removed from the agent
   registry, so Step 6a only `console.warn`s — yet the success message still claims
   "Tracking tickets created." Pre-existing/flaky failures are never tracked.

8. **P2 hygiene.** Baseline temp-worktree can leak on success/step-7 paths; main-side
   commits skip pre-commit hooks (no config probe); doc says "Step 5" while JS does
   "Step 6c"; brittle `JSON.parse` fallbacks can spuriously halt finalize.

### ADR cross-reference

- ADR-006 (`docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md`) — owns the
  depth-1/flatten decision; tickets 02 and 03 add addenda (pure-literal contract for
  workflow meta; finalize-feature joins epic-supervisor as a removed supervisor).

## Architecture Plan

### ADRs

- Addendum to ADR-006: (a) workflow scripts must declare a pure-literal `meta`,
  enforced by a gate (ticket 02); (b) `finalize-feature` agent is removed as a
  non-functional supervisor, JS workflow is the sole depth-0 executing context
  for finalization (ticket 03).

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_collapse_workflow_meta_literals.md](./01_collapse_workflow_meta_literals.md) | Collapse non-literal `meta` to pure literals in all 5 affected workflow scripts (unblocks finalize) | `[ ]` |
| 02 | [02_workflow_meta_literal_gate.md](./02_workflow_meta_literal_gate.md) | Add a test + pre-commit hook that fails on any non-literal `meta` node in `templates/workflows-js/*.js` | `[ ]` |
| 03 | [03_remove_dead_finalize_agent.md](./03_remove_dead_finalize_agent.md) | Remove/deprecate the finalize-feature agent fallback; slash command hard-errors when workflow support is absent | `[ ]` |
| 04 | [04_status_as_source_of_truth.md](./04_status_as_source_of_truth.md) | Stop physical folder moves on PR-only main in Step 6c; rely on frontmatter `status:` | `[ ]` |
| 05 | [05_gh_emu_preflight.md](./05_gh_emu_preflight.md) | Add `gh` account pre-flight (switch + verify, REST fallback) to finalize-feature.js | `[ ]` |
| 06 | [06_repo_root_detection.md](./06_repo_root_detection.md) | Replace CWD-trusting git detection with explicit repo-root anchoring in both scripts | `[ ]` |
| 07 | [07_bootstrap_dep_manager.md](./07_bootstrap_dep_manager.md) | Detect dependency manager (poetry vs pip) and make bootstrap non-fatal in setup_ticket_worktree.py | `[ ]` |
| 08 | [08_fix_dead_auto_ticketing.md](./08_fix_dead_auto_ticketing.md) | Fix Step 6a auto-ticketing (or honestly report it disabled); stop the false success message | `[ ]` |
| 09 | [09_finalize_p2_hygiene.md](./09_finalize_p2_hygiene.md) | P2 hygiene: baseline-worktree cleanup, pre-commit config probe, doc/code step-number drift, JSON.parse contracts | `[ ]` |
| 10 | [10_close_acs_on_finalize.md](./10_close_acs_on_finalize.md) | Close tickets (`status: done`) + source ACs (`work_status: done`) on the feature branch **before** the PR merge, so closure rides the PR to origin/main (no unpushable local-`main` write; no second PR). Closes the AC-first build loop | `[ ]` |

## Risk & Safety

- **Parallelism**: 01 is the unblocking P0 and should land first (or alongside 02).
  02 depends on 01 (the gate must pass once 01 is clean). 03, 05, 06, 07, 09 are
  independent of each other and of 01/02 (different files/concerns) and can run in
  parallel once authored.
- **finalize-feature.js serialization chain**: tickets 10, 04, and 08 all edit
  `templates/workflows-js/finalize-feature.js` (and its step-map doc), so they must
  run **serially**, not in the same parallel batch. Logical order: **10 → 04 → 08**.
  10 establishes pre-merge closure (ticket `status` + AC `work_status` on the feature
  branch); 04 then removes the now-redundant main-side moves/commits (`depends_on: 10`);
  08 fixes the dead Step 6a auto-ticketing. Each rebases on the prior to avoid
  same-file conflicts.
- Touches money? No.
- Touches data? No — workflow/agent/build tooling only. Ticket 04 changes how ticket
  files are (not) moved on main, but `status:` is already authoritative.
- Reversibility? High — all changes are to tooling scripts, agent templates, and a
  pre-commit hook; each is independently revertible.
