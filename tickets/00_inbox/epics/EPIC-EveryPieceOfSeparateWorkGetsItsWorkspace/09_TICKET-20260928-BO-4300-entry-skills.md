---
title: Entry skills and commands run the one maker and hand its answer to the workflow unchanged
status: done
components:
- worktree_manager
- skills_system
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 03_TICKET-20260928-BO-4300-answer-contract.md
- 06_TICKET-20260928-BO-4300-work-identity-and-ticket-location.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: prompt
risk_surface: contract_boundary
complexity: medium
requires_adr: false
requires_diagram: false
source_ac: BO-4300a-1-ib
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l3:
  - BO-4300a-1-ib
ac_coverage: 1/1
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- templates/commands/plan-feature.md
- templates/commands/build-feature.md
- templates/commands/fast-lane-build.md
- templates/commands/quick-fix.md
- templates/commands/finalize-feature.md
- templates/skills/plan-feature/SKILL.md
- templates/skills/quick-fix/SKILL.md
- templates/skills/build-single-ticket/SKILL.md
- templates/skills/feature/SKILL.md
- unit_tests/build_orchestration/test_bo_4300a_1_ib.py
- docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-1-ib.yaml
out_of_scope:
- scripts/build_deploy_manifest_helpers.py
- scripts/build_helpers.py
- scripts/build_phases_script_deploy.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_shim_env.py
- templates/scripts/commit_guardian/precommit_canary.py
- templates/scripts/workspace_root.py
- templates/scripts/worktree.py
- templates/scripts/worktree_admin.py
- templates/scripts/worktree_answer.py
- templates/scripts/worktree_canaries.py
- templates/scripts/worktree_git.py
- templates/scripts/worktree_identity.py
- templates/scripts/worktree_layout.py
- templates/scripts/worktree_paths.py
- templates/scripts/worktree_readiness.py
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_ii_fixtures.py
- unit_tests/build_orchestration/_developer_repo_guard.py
- unit_tests/build_orchestration/_workspace_maker_build_helpers.py
- unit_tests/build_orchestration/_workspace_maker_builders.py
- unit_tests/build_orchestration/_workspace_maker_fixtures.py
- unit_tests/build_orchestration/conftest.py
- unit_tests/build_orchestration/test_bo2400f_13i_own_leftover_report.py
- unit_tests/build_orchestration/test_bo_4300a_1.py
- unit_tests/build_orchestration/test_bo_4300a_1_deployed.py
- unit_tests/build_orchestration/test_bo_4300a_1_ii.py
- unit_tests/build_orchestration/test_bo_4300a_2.py
- unit_tests/build_orchestration/test_bo_4300b_1.py
- unit_tests/build_orchestration/test_bo_4300b_1_i.py
- unit_tests/build_orchestration/test_bo_4300b_2.py
- unit_tests/build_orchestration/test_bo_4300b_2_i.py
- unit_tests/build_orchestration/test_bo_4300b_2_ii.py
- unit_tests/build_orchestration/test_bo_4300b_3.py
- unit_tests/build_orchestration/test_bo_4300b_3_i.py
- unit_tests/build_orchestration/test_bo_4300b_4.py
- unit_tests/build_orchestration/test_bo_4300b_5.py
- unit_tests/build_orchestration/test_bo_4300b_5_i.py
- unit_tests/build_orchestration/test_bo_4300c_1.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_git_failure.py
- unit_tests/build_orchestration/test_bo_4300c_1_canary_order.py
- unit_tests/build_orchestration/test_bo_4300c_1_i.py
- unit_tests/build_orchestration/test_bo_4300c_1_ii.py
- unit_tests/build_orchestration/test_bo_4300c_1_iii.py
- unit_tests/build_orchestration/test_bo_4300c_1_marker_and_guardian.py
- unit_tests/build_orchestration/test_bo_4300c_1_path_keyed_canaries.py
- unit_tests/build_orchestration/test_bo_4300c_1_real_install.py
- unit_tests/build_orchestration/test_bo_4300c_1_review_fixes.py
- unit_tests/build_orchestration/test_bo_4300c_2.py
- unit_tests/build_orchestration/test_bo_4300d_3.py
- unit_tests/build_orchestration/test_bo_4300d_3_i.py
- unit_tests/build_orchestration/test_bo_4300d_4.py
- unit_tests/build_orchestration/test_bo_4300f_4.py
- unit_tests/build_orchestration/test_bo_4300f_4_i.py
agents:
  ac-fulfillment-gate: signed_off
  ac-validator: signed_off
  architect-review: signed_off
  commit: signed_off
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  llm-expert: signed_off
  pr-reviewer: signed_off
  pull-request: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
  user-surface-smoker: not_needed
---

# 09: Entry skills and commands run the one maker and hand its answer to the workflow unchanged

## Actor / Goal

In order that a workflow never has to make its own workspace when its entry already knows the work, we need each entry command/skill to run the maker once by absolute path, stop on a non-zero exit, and pass the answer verbatim as `args.workspace`, so that the workflow body only ever consumes a maker answer.

## Context

BO-4300a-1-ia (ticket 10) expects `args.workspace` from this AC; in the failed run ticket 02 blocked because `args.workspace` existed nowhere in templates (only the older `args.workspace_setup_permission`/`workspace_setup_agent`). a-1-ib is a child of BO-4300a-1 (ticket 01).

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 1 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300a-1-ib | L3 | Entry skills run the one maker and hand its answer to the workflow unchanged | BO-4300a-1 | 01_TICKET-20260927-BO-4300a-1.md |

**Closure order.** Children are listed before their parents. No composite AC in this ticket. `source_ac` (`BO-4300a-1-ib`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300a-1-ib (L3) -- Entry skills run the one maker and hand its answer to the workflow unchanged

```gherkin
Given an agent or a person starts a workflow that needs a workspace through its
  entry command or skill, or follows the workspace skill,
When a workspace is needed,
Then the workspace maker is run unchanged and its answer is passed on word for
  word as part of the workflow's input,
And no step asks an agent to create, copy, set up, link or repair a workspace
  by steps of the agent's own choosing.
```

- [x] AC-1: BO-4300a-1-ib -- Entry skills run the one maker and hand its answer to the workflow unchanged

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_command_published_by_each_deployed_entry_skill_runs_the_maker
  file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  covers:
  - BO-4300a-1-ib
  asserts: The single maker command each deployed entry skill/command publishes, executed as written against
    a temporary project, yields exactly one JSON object with status ok from the deployed maker.
  framework: unittest
  type: behavioral
  angle: deployed
  implementation_files:
  - templates/commands/plan-feature.md
  - templates/commands/build-feature.md
  - templates/commands/fast-lane-build.md
  - templates/commands/quick-fix.md
  - templates/commands/finalize-feature.md
  - templates/skills/plan-feature/SKILL.md
- name: test_deployed_workspace_skill_publishes_no_alternative_recipe
  file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  covers:
  - BO-4300a-1-ib
  asserts: The deployed workspace skill's text contains the one maker invocation and no clone, worktree,
    symlink, copy or build steps of its own (the text is this record's subject, so reading it is the behaviour).
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - templates/commands/plan-feature.md
  - templates/commands/build-feature.md
  - templates/commands/fast-lane-build.md
  - templates/commands/quick-fix.md
  - templates/commands/finalize-feature.md
  - templates/skills/plan-feature/SKILL.md
- name: test_build_single_ticket_step1_command_yields_ticket_inside_the_workspace
  file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  covers:
  - BO-4300a-1-ib
  asserts: The step-1 maker command the deployed build-single-ticket skill publishes, executed as written
    against a temp project whose hub holds a ticket, returns an ok answer whose ticket_path_in_worktree
    is inside workspace_path and names an existing file; the skill's text maps TICKET_PATH from that field
    and from no other.
  framework: unittest
  type: behavioral
  angle: deployed
  implementation_files:
  - templates/commands/plan-feature.md
  - templates/commands/build-feature.md
  - templates/commands/fast-lane-build.md
  - templates/commands/quick-fix.md
  - templates/commands/finalize-feature.md
  - templates/skills/plan-feature/SKILL.md
- name: test_no_deployed_entry_surface_spells_a_commit_with_dash_c
  file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  covers:
  - BO-4300a-1-ib
  asserts: No deployed entry skill or command this record lists contains `git -C <path> commit` (the text
    is the subject; the commit-delegation hook matches only the literal 'git commit').
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - templates/commands/plan-feature.md
  - templates/commands/build-feature.md
  - templates/commands/fast-lane-build.md
  - templates/commands/quick-fix.md
  - templates/commands/finalize-feature.md
  - templates/skills/plan-feature/SKILL.md
- name: test_ticket_09_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
  covers:
  - BO-4300a-1-ib
  angle: reachability
  surface_invoked: the deployed /plan-feature, /build-feature, /fast-lane-build, /quick-fix, /finalize-feature
    commands and the build-single-ticket/feature skills, with the maker command they publish executed
    for real
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - templates/commands/plan-feature.md
  - templates/commands/build-feature.md
  - templates/commands/fast-lane-build.md
  - templates/commands/quick-fix.md
  - templates/commands/finalize-feature.md
  - templates/skills/plan-feature/SKILL.md
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- THE workspace skill: repurpose `templates/skills/feature/SKILL.md` (one maker invocation, stop on non-zero, relay JSON) and delete its epic recipe and 'import settings' check. If a new skill is created instead it must be registered in `config/skill_registry.json` and this ticket's files_touched updated first.
- ONE command, absolute path (the path `worktree.py where` prints); never cwd-relative `python scripts/...`, never a compound shell command (prompt-audit).
- `templates/commands/plan-feature.md` calls the workflow without the pre-flight today, so that entry always stops with 'MISSING pre-flight' (a-1-ib it_requirements).
- TICKET LOCATION (same change set as BO-4300a-1-ii, ticket 06): build-single-ticket step 1 runs the maker with --ticket <main-copy path> and maps TICKET_PATH ONLY from `ticket_path_in_worktree`; delete the `ticket_path_final -> TICKET_PATH` mapping.
- Commit spelling: build-single-ticket, quick-fix and plan-feature skills spell `git -C <path> commit` today; delegate to the commit agent instead.
- INTERIM STATE: until ticket 10 lands, workflow bodies still read the old `workspace_setup_permission` args. All tickets land on the epic branch and ship as one PR, so no release sees the half state; do not add compatibility shims.
- Templates only; `.claude/` copies come from the build. Tests assert on the DEPLOYED skill/command text and on a real maker run (a-1-ib test_spec angles: deployed, criterion).

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300a-1-ib**

- Entry surfaces to change: templates/commands/plan-feature.md (today calls Workflow without the pre-flight, so that entry always stops with 'MISSING pre-flight'), templates/skills/plan-feature/SKILL.md, templates/commands/build-feature.md, templates/commands/fast-lane-build.md, templates/commands/quick-fix.md and templates/skills/quick-fix/SKILL.md, templates/commands/finalize-feature.md, templates/skills/build-single-ticket/SKILL.md, and templates/skills/feature/SKILL.md.
- Exactly one skill is THE workspace skill. Prefer repurposing the existing `feature` skill (one maker invocation, stop on a non-zero exit, relay the JSON answer) so no new package surface is registered; if a new skill is created instead, it must be registered in config/skill_registry.json and the feature skill reduced to a pointer.
- Each entry runs the maker as ONE command with an absolute path (the path `worktree.py where` prints, or the resolved install path) -- never a cwd-relative `python scripts/...` and never a compound shell command (prompt-audit checklist). On a non-zero exit it stops and does not invoke the workflow; on exit 0 it passes the parsed answer verbatim as args.workspace.
- Entries that cannot know the work identity before the workflow resolves it (e.g. build-feature's epic resolution) leave the workspace to the workflow's one verbatim dispatch (BO-4300a-1-ia); the skill text must not describe any other way.
- No surface keeps its own step-by-step recipe (clone, worktree add, symlink or copy of .leafcutter / .pre-commit-config.yaml, manual build); the epic recipe in the feature skill and its project-specific 'import settings' check are deleted.
- Skill and command templates reach consumers only through the build; edit templates/, never .claude/ directly.
- TICKET LOCATION (KI-BO-20260925-build-single-ticket-treats-ticket-path-final-as-worktree-path; routed from BO-4300a-1-ii, lands in the SAME change set as it): templates/skills/build-single-ticket/SKILL.md's step 1 runs the maker with --ticket <the ticket's main-copy path> and maps TICKET_PATH ONLY from ticket_path_in_worktree of the ok answer. The 'ticket_path_final -> TICKET_PATH (the ticket's path inside the worktree)' mapping is deleted, and no step of the skill reads, edits or moves the ticket at the path it was given.
- Commit spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): no entry surface this record rewrites spells a commit as `git -C <path> commit` (build-single-ticket, quick-fix and plan-feature skills carry that spelling today); commits are delegated to the commit agent per CLAUDE.md Commit Delegation. -C is acceptable only for non-commit git verbs.

## Agent Contracts

### llm-expert

- [x] AC-1: BO-4300a-1-ib -- Entry skills run the one maker and hand its answer to the workflow unchanged <!-- signed: llm-expert -->

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [x] AC-1: red tests for BO-4300a-1-ib per `## Test Requirements`

**Delivers to:** llm-expert (red baseline).

### Expects From

- **BO-4300a-1-ib <- BO-4300a-1** (01_TICKET-20260927-BO-4300a-1.md): CLI of the one maker. Deployed at <install-root>/scripts/worktree.py (source templates/scripts/worktree.py; the name is provisional until this AC is built, after which that path is the contract every caller names). Stdlib-only Python, run as `python <absolute path> <verb> ...` from ANY cwd. Verbs: `ensure --kind {ticket|feature|ac|fastlane|epic|scratch} --slug <work identity> [--repo-root P] [--allow-stale-base] [--config-path P]` -- the only creating verb, idempotent, always fetch + build + canary; `locate (--kind K --slug S | --path P | --branch B) [--repo-root P]` -- read-only; `list [--repo-root P]` -- read-only scan of the landing place's markers, never git worktree list; `verify --path P [--kind K --slug S] [--repo-root P]` -- read-only readiness re-check; `remove --path P [--discard-token T] [--delete-remote-branch] [--repo-root P]` -- T is the one-time token from this same workspace's own UNSENT_WORK refusal (Q8, decided 2026-09-28, BO-4300e-3); `where` -- prints the maker's own absolute path. ensure, locate, list, verify and remove also accept [--landing-root P], the explicit landing-place override the maker validates (Q5, decided 2026-09-28, BO-4300b-2); --kind K --slug S is normalised to the one identity <kind>/<slug>, legacy spellings accepted as aliases (Q4, decided 2026-09-28, BO-4300a-2). There is no --reset-existing (BO-4300d-4 resumes), no --no-bootstrap (decision 2), and no flag that skips a readiness ingredient.

### Delivers To

- **BO-4300a-1-ib -> python-coder**: args.workspace on every workflow invocation that can know its work identity up front: the maker's ensure answer as a JSON object, unmodified (BO-4300c-2 shape). The workflow applies the BO-4300c-3 acceptance predicate to it.
- consumed by **BO-4300a-1-ia** in 10_TICKET-20260928-BO-4300-workflow-runtime-and-shell-runner.md
- consumed by **BO-4300f-1** in 11_TICKET-20260928-BO-4300-workflow-routes.md

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_bo_4300a_1_ib.py:test_command_published_by_each_deployed_entry_skill_runs_the_maker; test_deployed_workspace_skill_publishes_no_alternative_recipe; test_build_single_ticket_step1_command_yields_ticket_inside_the_workspace; test_no_deployed_entry_surface_spells_a_commit_with_dash_c; test_ticket_09_reachable_from_entry_point | Rewrote feature skill to one maker invocation; entry commands/skills run the maker once and pass args.workspace; build-single-ticket maps TICKET_PATH only from ticket_path_in_worktree | ok — 2026-10-10 |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [x] architect-review — 2026-10-10 12:00
- [x] test-writer — 2026-10-10 13:00
- [x] llm-expert — 2026-10-10 18:20
- [x] test-runner — 2026-10-10 19:00
- [x] pr-reviewer — 2026-10-10 18:26
- [x] ac-validator — 2026-10-10 19:30
- [x] ac-fulfillment-gate — 2026-10-10 20:00
- [x] commit — 2026-10-10 20:30

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-10 12:00 — architect-review (status: ok)
feedback-id: fb_2026-10-10_749541f6
completion_manifest:
  rubric_evaluated: true
  research_agent_spawned:
    result: false
    reason: "Agent tool unavailable in this phase; blast radius taken from the ticket's own files_touched and targeted greps."
    remediation: "None needed; scope is prompt templates only."
Classification: LARGE by threshold (10 files > 5); no always-large trigger fired (no Alembic, hypertable, FastAPI or ADR-file change). Opus deep review not spawned (no Agent tool); escalation recorded as opus-by-threshold for the supervisor. Components: worktree_manager and skills_system (2). requires_adr stays false: the maker contract is owned by the existing worktree-maker amendment ADR and this ticket only consumes it; no new cross-cutting policy. Design concerns: build-single-ticket (lines ~79, 369, 375) and quick-fix still carry the ticket_path_final mapping and the dash-C commit spelling and must be rewritten; plan-feature command must pass args.workspace; feature skill must be reduced to the single maker invocation. Acceptance adjustments: none. suggested_adr: null; suggested_diagrams: [].

### 2026-10-10 18:20 — llm-expert (status: ok)
feedback-id: fb_2026-10-10_9c21dc62
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
Reduced the feature skill to the one maker invocation; plan-feature, fast-lane-build and quick-fix commands plus the plan-feature, quick-fix and build-single-ticket skills now run `worktree.py ensure` once by absolute path, stop on non-zero, and pass the answer as args.workspace. build-feature and finalize-feature leave the workspace to the workflow. build-single-ticket maps TICKET_PATH only from ticket_path_in_worktree, and the dash-C commit spellings and old creation recipes are gone. The new test module passes (5 passed) against the deployed build.

### 2026-10-10 19:00 — test-runner (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Suite: unit_tests/build_orchestration/test_bo_4300a_1_ib.py (routed by files_touched; templates + build_orchestration). Tests run: 5   Failures: 0   Errors: 0   Skipped: 0 (104 subtests passed). Elapsed: 106.6s.

## Escalation

Branch: opus
Reason: affected files (10) exceed the 5-file threshold; no always-large trigger.

### 2026-10-10 13:00 — test-writer (status: ok)
feedback-id: fb_2026-10-10_2f221244
completion_manifest:
  red_tests_written: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "deployed worktree.py ensure answer (ticket_path_in_worktree, workspace_path)"
    consuming_side: "deployed build-single-ticket skill text / entry command that maps it to TICKET_PATH and args.workspace"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "the maker command published in deployed .claude/commands/plan-feature.md, executed as written via subprocess against a temp hub project"
red_baseline:
  - test_name: test_deployed_workspace_skill_publishes_no_alternative_recipe
    file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
    kind: assertion
    error: "AssertionError: ... still spells setup_ticket_worktree\.py (non-strict run: xfailed; strict run: failed)"
  - test_command_published_by_each_deployed_entry_skill_runs_the_maker
    file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
    kind: assertion
    error: "AssertionError: expected exactly one maker command, got [] (per-surface subtests)"
  - test_ticket_09_reachable_from_entry_point
    file: unit_tests/build_orchestration/test_bo_4300a_1_ib.py
    kind: assertion
    error: "AssertionError: plan-feature must pass args.workspace"
Five tests written in unit_tests/build_orchestration/test_bo_4300a_1_ib.py against the DEPLOYED surfaces (shared ensure_deployed_layout build). Non-strict run: 2 passed, 30 xfailed. Strict run hit DeployedMakerNotFoundError (build timeout under load) for part of it; rerun strict when idle.

### 2026-10-10 18:26 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-10_baecf076
completion_manifest:
  review_run: true
  high_findings: 0
Reviewed the entry-surface diff (5 commands, 4 skills, new test module). Contract pass: every maker invocation is one absolute-path worktree.py ensure with a valid verb, kind and flags per Expects From; non-zero exit stops; answer passed verbatim as workspace; build-single-ticket maps TICKET_PATH only from ticket_path_in_worktree; no dash-C commit spelling, clone, symlink or copy recipes remain. 5 tests pass (104 subtests). No high-confidence findings. [M-1] Cross-file: the workflows that consume args.workspace (tickets 10 and 11) are outside this diff and not verifiable here. [M-2] The working tree also carries unrelated changes (precommit_canary.py, 4300c/4300d tests, tickets 07 and 15) that belong to other tickets; keep them out of this ticket's commit. Suppressed: 0 low. Escalation: not escalated, medium count 2 (threshold > 3).

### 2026-10-10 19:30 — ac-validator (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_coverage_checked: true
  store_alignment_exit: 0
All 1 ACs covered.
AC-1 covered:
  implementation: templates/commands/plan-feature.md (Workflow plan-feature with workspace: maker-answer, worktree.py ensure); templates/skills/build-single-ticket/SKILL.md:82 (ticket_path_in_worktree -> TICKET_PATH); templates/skills/feature/SKILL.md reduced to one maker invocation; no dash-C commit spelling or ticket_path_final remaining in the listed surfaces.
  test: test_command_published_by_each_deployed_entry_skill_runs_the_maker, test_deployed_workspace_skill_publishes_no_alternative_recipe, test_build_single_ticket_step1_command_yields_ticket_inside_the_workspace, test_no_deployed_entry_surface_spells_a_commit_with_dash_c, test_ticket_09_reachable_from_entry_point (unit_tests/build_orchestration/test_bo_4300a_1_ib.py, covers: BO-4300a-1-ib)
Store alignment script exit 0. Contract note: consumers of args.workspace (tickets 10, 11) are outside this diff. Unrelated staged changes (test_bo_4300d_*, tickets 07/15, precommit_canary.py) belong to other tickets and must stay out of this ticket's commit.

### 2026-10-10 20:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  ac_store_verified: true
All 1 L3 ACs verified. BO-4300a-1-ib: work_status done (mark_ac_done.py: 'marked BO-4300a-1-ib work_status=done'; first attempt refused on a transient reachability-test error, passed standalone and on retry), implemented_by auto-fixed (appended 9 files_touched template paths), covered_by auto-fixed (appended unit_tests/build_orchestration/test_bo_4300a_1_ib.py). check_ac_schema exit 0. 2 auto-fixes applied. Commit phase may proceed.

### 2026-10-10 20:30 — commit (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "feat(entry): entry skills run the one maker and hand its answer to the workflow unchanged"; committed by explicit path so unrelated staged work (ticket 07, 4300d tests, 4300c-6) stays out, per pr-reviewer M-2.
