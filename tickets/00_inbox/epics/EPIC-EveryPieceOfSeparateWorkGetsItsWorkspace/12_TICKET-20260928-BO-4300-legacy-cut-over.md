---
title: 'Cut-over: workspaces made the old way are brought over or retired without losing work'
status: todo
components:
- worktree_manager
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 08_TICKET-20260928-BO-4300-locate-and-clear.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: high
requires_adr: false
requires_diagram: false
source_ac: BO-4300f-3
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-3
  l3:
  - BO-4300f-3-i
  - BO-4300f-3-ii
ac_coverage: 0/3
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/scripts/worktree.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_migrate.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
- unit_tests/build_orchestration/test_bo_4300f_3.py
- unit_tests/build_orchestration/test_bo_4300f_3_i.py
- unit_tests/build_orchestration/test_bo_4300f_3_ii.py
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
---

# 12: Cut-over: workspaces made the old way are brought over or retired without losing work

## Actor / Goal

In order to switch every existing project to the one way without losing work, we need a cut-over verb on the same maker that retires or brings over each legacy git worktree and protects shared history until it is done, so that no unsent commit or file is lost during the migration.

## Context

In the failed run ticket 56 blocked because neither the `migrate-legacy` verb (f-3) nor the legacy-worktree fixture (f-4) existed. Both producers now come earlier (ticket 02 fixture, this ticket the verb).

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 3 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300f-3-i | L3 | Running the cut-over again changes nothing further | BO-4300f-3 | this ticket |
| AC-2 | BO-4300f-3-ii | L3 | Until the cut-over completes, automatic housekeeping cannot prune the shared history | BO-4300f-3 | this ticket |
| AC-3 | BO-4300f-3 | L2 | Workspaces made the old way are brought over or retired without losing work | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300f-3` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300f-3`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300f-3-i (L3) -- Running the cut-over again changes nothing further

```gherkin
Given the cut-over has run once to completion,
When it is run a second time,
Then no workspace is retired, brought over or changed,
And its report states that there is nothing left to do other than the
  workspaces already listed as needing a decision.
```

### AC-2: BO-4300f-3-ii (L3) -- Until the cut-over completes, automatic housekeeping cannot prune the shared history

```gherkin
Given old-style workspaces still share the main copy's version history,
When enough commits are made in the main copy that version control's automatic
  housekeeping would otherwise start,
Then that housekeeping does not run until the cut-over has retired or brought
  over the last old-style workspace,
And every commit each old-style workspace refers to is still readable afterwards.
```

### AC-3: BO-4300f-3 (L2) -- Workspaces made the old way are brought over or retired without losing work

```gherkin
Given a project with 19 workspaces made the old way -- some holding work that
  has not reached the shared project and some holding none -- and 2 entries in
  the project's workspace register that were started from a Linux shell and
  never finished,
When the cut-over is run,
Then each old workspace holding nothing unsent is retired: its folder is gone
  and its register entry is gone,
And each old workspace holding unsent work is either brought over as a
  workspace the one maker recognises, with that work intact, or left untouched
  and listed as needing a decision,
And the 2 unfinished entries are gone from the register, and nothing else is
  changed by their removal,
And afterwards the register of old-style workspaces lists only those left for a
  decision.
```

- [ ] AC-1: BO-4300f-3-i -- Running the cut-over again changes nothing further
- [ ] AC-2: BO-4300f-3-ii -- Until the cut-over completes, automatic housekeeping cannot prune the shared history
- [ ] AC-3: BO-4300f-3 -- Workspaces made the old way are brought over or retired without losing work

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_second_cutover_run_changes_nothing
  file: unit_tests/build_orchestration/test_bo_4300f_3_i.py
  covers:
  - BO-4300f-3-i
  asserts: Worktree registrations, folders and refs are identical before and after the second run.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_second_run_report_says_nothing_left_but_listed_decisions
  file: unit_tests/build_orchestration/test_bo_4300f_3_i.py
  covers:
  - BO-4300f-3-i
  asserts: The second report lists no retired or brought_over entries and repeats needs_decision.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_automatic_housekeeping_does_not_run_while_legacy_workspaces_remain
  file: unit_tests/build_orchestration/test_bo_4300f_3_ii.py
  covers:
  - BO-4300f-3-ii
  asserts: After commits that would trigger gc --auto, the loose-object count and pack set are unchanged.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_every_commit_referenced_by_legacy_workspaces_stays_readable
  file: unit_tests/build_orchestration/test_bo_4300f_3_ii.py
  covers:
  - BO-4300f-3-ii
  asserts: cat-file -e succeeds for every such commit afterwards.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_previous_housekeeping_settings_restored_after_last_legacy_retired
  file: unit_tests/build_orchestration/test_bo_4300f_3_ii.py
  covers:
  - BO-4300f-3-ii
  asserts: Once no legacy workspace remains, gc.auto and maintenance.auto have their recorded previous
    values.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_workspace_with_nothing_unsent_is_retired_folder_and_registration
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: Each such legacy worktree's folder and .git/worktrees entry are gone.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_legacy_workspace_with_unsent_work_is_brought_over_intact_or_listed
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: Each such worktree is either a marker-bearing clone containing every original commit sha and
    identical uncommitted content, or untouched and listed in needs_decision.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_unfinished_foreign_platform_entries_are_removed_and_nothing_else_changes
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: The two stuck admin entries are gone; all other refs, worktrees and config are identical.
  framework: unittest
  type: behavioral
  angle: boundary
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_old_style_register_lists_only_workspaces_left_for_decision
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: git worktree list afterwards lists only the needs_decision entries (plus the main checkout).
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_brought_over_workspace_lands_at_its_canonical_location_keeping_its_branch
  file: unit_tests/build_orchestration/test_bo_4300f_3.py
  covers:
  - BO-4300f-3
  asserts: A legacy worktree on EPIC-Alpha holding an unpushed commit, brought over, is a marker-bearing
    clone at <landing-root>/epic/alpha (not in the legacy folder) on branch EPIC-Alpha with the commit
    intact, and a later ensure --kind epic --slug alpha answers ok with that same workspace_path and line_of_work
    existing or resumed.
  framework: unittest
  type: behavioral
  angle: criterion
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
- name: test_ticket_12_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300f_3_i.py
  covers:
  - BO-4300f-3
  angle: reachability
  surface_invoked: python <install-root>/.leafcutter/scripts/worktree.py migrate-legacy [--preview] --repo-root
    <project> (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/scripts/worktree.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_migrate.py
  - scripts/build_phases_script_deploy_standalone.py
  - scripts/build_deploy_manifest_helpers.py
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- VERB: `worktree.py migrate-legacy` in `templates/scripts/worktree_migrate.py` (named deploy entry); the ONLY place allowed to run `git worktree` commands, and only against legacy entries (ticket 14's census declares it exempt). Holds-work verdict = BO-4100c-1, reuse the unsent-work classifier ticket 08 exports from `worktree_remove.py` (import, do not copy).
- Preview mode that changes nothing; report is one JSON object listing retired, brought_over and needs_decision; stuck WSL 'locked initializing' admin entries removed individually. Re-running changes nothing further (f-3-i).
- HOUSEKEEPING (f-3-ii): set `gc.auto 0` and `maintenance.auto false` on the main checkout while any legacy workspace remains (ADR-018 migration step 2, never applied), record and restore previous values; proof triggers real auto-gc past a lowered threshold and `git cat-file -e`s every referenced commit.
- Uses ticket 02's legacy-worktree fixture helper; no test here spells the worktree add/remove commands itself.
- STARTING POINT (re-verify): `git show refs/wip/bo4300-attempt1:unit_tests/build_orchestration/test_bo_4300f_3_i.py`.
- FILE-SIZE RATCHET: `templates/scripts/worktree.py` is at ~393 of 400 counted lines and `templates/scripts/worktree_git.py` near its limit (01 python-coder sign-off). Every addition therefore goes into the NEW module this ticket owns (see files_touched); the two core files are touched only to move code out and to wire the new module in. A new module needs its own NAMED deploy entry in `scripts/build_phases_script_deploy_standalone.py` and `scripts/build_deploy_manifest_helpers.py` (KI-TQ-004: no second tracked copy; the maker is deployed to `<install-root>/.leafcutter/scripts/<name>`, not `<install-root>/scripts/`, per 01 test-writer/python-coder).
- ANSWER TABLE: the status/code/exit table is owned by ticket 03 (BO-4300c-2 declares the full code enum). Do not add codes locally; if a code is missing from BO-4300c-2 it is a contract change, not a local edit.
- PROOF: tests run the DEPLOYED maker through ticket 02's locator (`unit_tests/build_orchestration/_workspace_maker_fixtures.py`), as a subprocess, against real temp repos with a real bare hub; no mock of git, no import of the maker module, never spawn `scripts/build.py`. Pin `newline="\n"` on fixture writes and isolate GIT_CONFIG_GLOBAL/GIT_CONFIG_NOSYSTEM (the CRLF drift found on 04 in the failed run). Use `AC_ENFORCE_STRICT=1` to see a genuine red baseline (the AC-enforcement plugin otherwise downgrades not-done-AC failures to xfail).
- HOOK HYGIENE (lessons from ticket 01): DECISION HISTORY entries need `HH:MM` and the `(#EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/NN)` tail-tag on the entry's FIRST line; run `check_documentation.py` with NO `--file` flag (staged mode) before commit; run `check_doc_length.py` on every doc touched (300-line ratchet); stage every file in files_touched (01 shipped an ADR edit unstaged). Commits never spelled `git -C <path> commit`.
- SCOPE: the epic worktree is shared by every ticket. Edit only files_touched. If the fix needs another file, stop and get this ticket updated (CLAUDE.md TICKET MANDATE); the failed run stalled on exactly this (tickets 04, 14, 46, 59).

- USER DECISIONS (2026-09-28) FOR THE CUT-OVER: Q4 (`<kind>/<slug>` identity with per-kind legacy aliases, ticket 06) and Q5 (sibling landing root `<parent-of-project>/<project-dir-name>-worktrees/`, ticket 04). A legacy worktree brought over becomes a marker-bearing clone at `<landing-root>/<kind>/<slug>` for the identity its legacy branch maps to through ticket 06's alias table -- never in the legacy folder -- and keeps its existing branch name. A legacy branch no declared alias maps to is listed `needs_decision`, never guessed. Use ticket 06's naming table and ticket 04's layout rule; do not re-implement either.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300f-3-i**

- Idempotent: a second run is a no-op and its report (excluding timestamps) is byte-stable across further runs.

**BO-4300f-3-ii**

- The cut-over sets gc.auto 0 and maintenance.auto false on the main checkout while any legacy workspace remains (ADR-018 migration step 2, never applied), records the previous values, and restores them only after the last legacy workspace is retired or brought over.
- Proof triggers git's automatic housekeeping for real (enough loose objects past a lowered threshold) and checks every commit each legacy workspace refers to with `git cat-file -e`.

**BO-4300f-3**

- The cut-over is reachable through the same door: a maker verb (e.g. `worktree.py migrate-legacy`) rather than a second script; if a separate script is chosen it must be a named deploy-manifest entry. It is the ONLY place allowed to run `git worktree` commands, and only against legacy entries.
- Per legacy workspace, the BO-4100c-1 holds-work verdict decides: nothing unsent -> remove its folder and its registration; unsent work -> bring over as a marker-bearing clone ONLY when provably lossless (every commit sha present on the new line, uncommitted and untracked content byte-identical), otherwise leave untouched and list for a human decision (Q10: never retired while it holds unsent work).
- BRING-OVER TARGET (Q4 + Q5, DECIDED user 2026-09-28): a workspace brought over lands where the maker would put it -- <landing-root>/<kind>/<slug> for its canonical identity, landing root per BO-4300b-2 -- never in the legacy folder; its identity is taken from the legacy branch through the one naming table's declared aliases (BO-4300a-2). The line of work keeps its existing branch name (never renamed, so no open pull request or hub ref is orphaned), and the marker records that branch. A legacy branch that no declared alias maps to is not guessed: it is left untouched and listed as needing a decision.
- Stuck registration entries made from another platform (the WSL 'locked initializing' admin entries) are removed individually; nothing else is touched by their removal.
- Offers a no-change preview of what it would do; its report is one JSON object listing retired, brought_over and needs_decision entries.
- Must handle errors per the project error handling policy: a condition the maker cannot classify is an error answer (code INTERNAL_ERROR) whose message names it -- never an ok answer, and never a traceback on stdout.

## Agent Contracts

### python-coder

- [ ] AC-1: BO-4300f-3-i -- Running the cut-over again changes nothing further
- [ ] AC-2: BO-4300f-3-ii -- Until the cut-over completes, automatic housekeeping cannot prune the shared history
- [ ] AC-3: BO-4300f-3 -- Workspaces made the old way are brought over or retired without losing work

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300f-3-i per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300f-3-ii per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300f-3 per `## Test Requirements`

**Delivers to:** python-coder (red baseline).

### Expects From

- **BO-4300f-3-i <- BO-4300f-3** (this ticket): Cut-over report JSON.
- **BO-4300f-3-ii <- BO-4300f-3** (this ticket): Cut-over lifecycle (legacy workspaces remaining vs none).
- **BO-4300f-3 <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): ensure/marker format for brought-over workspaces.

### Delivers To

- none

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? Yes -- workspaces can hold unsent work; every destructive path refuses unless authorised, and proofs run only in temp repos.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
