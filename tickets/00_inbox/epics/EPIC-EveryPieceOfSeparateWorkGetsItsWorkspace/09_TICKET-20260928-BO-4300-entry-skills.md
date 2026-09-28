---
title: Entry skills and commands run the one maker and hand its answer to the workflow unchanged
status: todo
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
ac_coverage: 0/1
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
agents:
  ac-fulfillment-gate: needed
  ac-validator: needed
  architect-review: needed
  commit: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  frontend-coder: not_needed
  llm-expert: needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
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

- [ ] AC-1: BO-4300a-1-ib -- Entry skills run the one maker and hand its answer to the workflow unchanged

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

- [ ] AC-1: BO-4300a-1-ib -- Entry skills run the one maker and hand its answer to the workflow unchanged

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300a-1-ib per `## Test Requirements`

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
| AC-1 | | | |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] test-writer
- [ ] llm-expert
- [ ] test-runner
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
