---
title: 'The former ways are gone: retire the old scripts, census the repo, rewrite every written recipe'
status: todo
components:
- worktree_manager
- build_pipeline
- skills_system
created: '2026-09-28'
last_updated: '2026-09-28'
depends_on:
- 01_TICKET-20260927-BO-4300a-1.md
- 11_TICKET-20260928-BO-4300-workflow-routes.md
- 12_TICKET-20260928-BO-4300-legacy-cut-over.md
- 13_TICKET-20260928-BO-4300-docs-and-diagrams.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: contract_boundary
complexity: high
requires_adr: true
requires_diagram: false
source_ac: BO-4300f-2
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300f-2
  l3:
  - BO-4300f-2-ia
  - BO-4300f-2-ib
ac_coverage: 3/3
tags:
- BO-4300
- re-cut-2026-09-28
files_touched:
- scripts/setup_ticket_worktree.py
- templates/scripts/setup_ticket_worktree.py
- templates/scripts/worktree_repo_facts.py
- tests/test_setup_ticket_worktree.py
- unit_tests/test_setup_ticket_worktree.py
- unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py
- unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
- unit_tests/workflows/test_bo4000b_branch_staleness_decision.py
- unit_tests/workflows/test_bo4000c_start_location_and_occupancy.py
- unit_tests/workflows/test_bo4000d_facts_envelope_depth.py
- templates/scripts/git_recovery.py
- tests/test_git_recovery.py
- scripts/worktree/check_workspace_setup_permission.py
- scripts/worktree/README.md
- scripts/build.py
- scripts/build_phases.py
- scripts/build_phases_script_deploy.py
- scripts/build_phases_workflows.py
- scripts/build_helpers.py
- templates/scripts/commit_guardian/commit_guardian.json
- unit_tests/build_orchestration/test_bo_4300f_2.py
- unit_tests/build_orchestration/test_bo_4300f_2_ia.py
- unit_tests/build_orchestration/test_bo_4300f_2_ib.py
- CLAUDE.md
- README.md
- templates/agents/worktree-agent.md
- templates/agents/epic-supervisor.md
- templates/skills/feature/SKILL.md
- templates/skills/building-epics/SKILL.md
- templates/skills/build-feature-ops-notes/SKILL.md
- templates/skills/ship/SKILL.md
- templates/skills/plan-feature/SKILL.md
- templates/skills/quick-fix/SKILL.md
- templates/workflows/close-worktree.md
- templates/workflows/build-backlog.md
- templates/workflows/worktree.md
- templates/workflows-js/finalize-feature.js
- templates/workflows-js/plan-feature.js
- templates/workflows-js/quick-fix.js
- docs/how-to/drive-epic-manually.md
- docs/how-to/verify-precommit-active.md
- docs/reference/plan-feature-layout-and-startup-checks.md
- docs/reference/skills-config-fields.md
- docs/agents/utility/worktree-agent.md
- docs/agents/cards/workflow-architect.card.md
- docs/architecture/agent_delivery_workflows.md
- docs/architecture/components/worktree-manager.md
- docs/architecture/components/worktree-quality-gate-guard.md
- docs/architecture/components/template-compiler.md
- docs/architecture/adrs/ADR-001-self-hosting-boundary.md
- docs/INDEX.md
- config/skills_config.schema.json
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
- unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py
- unit_tests/build_orchestration/test_bo2400f_13iii_refusal_is_inert.py
- unit_tests/build_orchestration/test_bo2400f_13iv_free_location_proceeds.py
- unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py
- unit_tests/build_orchestration/test_fastlane_worktree_mode.py
- unit_tests/commit_guardian/test_check_doc_frontmatter_worktree_pathbase.py
- unit_tests/feedback/test_submit_feedback_worktree_resolution.py
- unit_tests/portability/_bp900h4_layout_helpers.py
- unit_tests/portability/_deployed_check_harness.py
- unit_tests/portability/test_bp_900h_4_i.py
- unit_tests/portability/test_ge120c1i_setup_failure_reporting.py
- unit_tests/portability/test_ge_120e_1.py
- unit_tests/portability/test_ge_120e_1_i.py
- unit_tests/portability/test_ge_120e_4.py
- unit_tests/workflows/test_acd_2100a_1.py
- unit_tests/workflows/test_acd_2100a_3.py
- unit_tests/workflows/test_acd_2100a_4.py
- unit_tests/workflows/test_acd_2100a_5.py
- unit_tests/workflows/test_acd_2100c_2.py
- unit_tests/workflows/test_acd_2100c_3.py
- unit_tests/workflows/test_acd_2100c_3_i.py
- unit_tests/workflows/test_fin_100h_refusal_not_success.py
- unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
- unit_tests/workflows/test_quick_fix_worktree_invariant.py
- tests/test_sweep_processes.py
- scripts/build_phases_script_deploy_standalone.py
- scripts/build_deploy_manifest_helpers.py
agents:
  ac-fulfillment-gate: signed_off
  ac-validator: signed_off
  adr-author: signed_off
  architect-review: signed_off
  commit: signed_off
  documentation-expert: signed_off
  documentation-verifier: signed_off
  frontend-coder: not_needed
  llm-expert: signed_off
  pr-reviewer: signed_off
  pull-request: not_needed
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  test-writer: signed_off
  user-surface-smoker: not_needed
red_baseline_gate: {"passed": true, "recorded_at": "2026-10-14T06:35:08+00:00", "head": "cc3c85edc3edfae7528fa43bbff64592e2ddfb35", "source_ac": ["BO-4300f-2"], "red": [{"file": "unit_tests/build_orchestration/test_bo_4300f_2.py", "function": "test_no_git_worktree_add_or_remove_outside_the_declared_exemptions"}, {"file": "unit_tests/build_orchestration/test_bo_4300f_2.py", "function": "test_no_git_dash_c_commit_in_component_files_or_instruction_surfaces"}, {"file": "unit_tests/build_orchestration/test_bo_4300f_2_ia.py", "function": "test_ticket_14_reachable_from_entry_point"}]}
---

# 14: The former ways are gone: retire the old scripts, census the repo, rewrite every written recipe

## Actor / Goal

In order that there is exactly one way to get a workspace, we need the former scripts gone (or shimmed to the maker for one release), a repo-wide census that fails on any `git worktree add/remove` outside the declared exemptions, and every charter, skill, workflow text, how-to and the rules file pointing at the maker, so that no second recipe survives.

## Context

f-2 expects from f-1 (ticket 11); f-2-ia/ib expect from a-3 (ticket 13); the census exempts only ticket 12's cut-over verb and ticket 02's legacy fixture helper. It runs last. f-2-i (superseded by f-2-ia/ib) was removed from BO-4300f-2's covered_by in this re-cut so f-2 can close.

Part of `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, re-cut on 2026-09-28 by deliverable (see Master_Plan.md, 'Re-cut 2026-09-28'). This ticket owns the files in `files_touched` and covers 3 AC(s); the AC YAML records under `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` are the source of truth and win over any text here.

## AC References

| # | AC | Level | Title | Expects from | Producing ticket |
|---|----|-------|-------|--------------|------------------|
| AC-1 | BO-4300f-2-ia | L3 | Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces | BO-4300a-3 | 13_TICKET-20260928-BO-4300-docs-and-diagrams.md |
| AC-2 | BO-4300f-2-ib | L3 | How-to guides carry no second recipe for workspaces | BO-4300a-3 | 13_TICKET-20260928-BO-4300-docs-and-diagrams.md |
| AC-3 | BO-4300f-2 | L2 | The former ways of making a workspace are gone from what an install delivers | BO-4300f-1 | 11_TICKET-20260928-BO-4300-workflow-routes.md |

**Closure order.** Children are listed before their parents. Composite(s) `BO-4300f-2` close only after every child listed in their `covered_by` is done (`check-done-proof`); all of those children are in this ticket, so no parent here waits on another ticket. `source_ac` (`BO-4300f-2`) is the anchor `check-ticket-ac-status-parity` checks; `ac_traceability` (list form) names every AC so `ac-fulfillment-gate` verifies each one before commit. The ticket may be set `done` only when every AC above is `work_status: done`.

## Acceptance Criteria

### AC-1: BO-4300f-2-ia (L3) -- Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces

```gherkin
Given the instructions an install delivers to agents and people -- agent
  charters, skills, workflow texts and the project rules file,
When each passage about making, finding or clearing a workspace is read,
Then it directs the reader to the one workspace maker and to the how-to guide
  for getting a workspace,
And none gives its own steps to copy the project, start a line of work,
  install tools into a workspace, link or copy protection settings into one, or
  delete one by hand.
```

### AC-2: BO-4300f-2-ib (L3) -- How-to guides carry no second recipe for workspaces

```gherkin
Given the instructions an install delivers to agents and people -- how-to
  guides,
When each passage about making, finding or clearing a workspace is read,
Then it directs the reader to the one workspace maker and to the how-to guide
  for getting a workspace,
And none gives its own steps to copy the project, start a line of work,
  install tools into a workspace, link or copy protection settings into one, or
  delete one by hand.
```

### AC-3: BO-4300f-2 (L2) -- The former ways of making a workspace are gone from what an install delivers

```gherkin
Given a fresh project that has installed these tools,
When each former way of making, finding or clearing a workspace is invoked by
  the name an install used to deliver it under -- the former workspace set-up
  script and each of its sub-commands, the workspace-facts helper's base
  lookup, and the recovery fallback that re-adds a workspace --
Then each is either absent from the install, or, for at most one release,
  passes the request to the one workspace maker and returns the maker's answer
  unchanged,
And no former way makes, finds or clears a workspace by its own means.

Given the project's own files -- its code, templates, skills, agents,
  commands, workflows, how-to guides, reference and component documentation,
  READMEs and CLAUDE.md,
When the census of the old way of creating or removing a workspace (adding or
  removing a git worktree) is run over the project,
Then no file creates or removes a workspace the old way, in any spelling -- a
  shell line, the form that names a folder first, an argument list, a script
  template or a written instruction to an agent,
And the only exempt sites are the one-off cut-over step (BO-4300f-3) and the
  one test helper that builds a legacy workspace for that step's tests, each
  entered with its reason in one declared exemption list,
And records of the past -- analyses, known issues, retrospectives, changelogs,
  architecture decision records, tickets and acceptance criteria -- are out of
  scope, excluded by folder in
  that same declared list and never file by file, so an old-way instruction
  added to a how-to guide is reported while the same text quoted in an
  analysis is not,
And each hit is reported by file and line.
```

- [x] AC-1: BO-4300f-2-ia -- Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces
- [x] AC-2: BO-4300f-2-ib -- How-to guides carry no second recipe for workspaces
- [x] AC-3: BO-4300f-2 -- The former ways of making a workspace are gone from what an install delivers

## Test Requirements

Taken from each AC's `test_spec` (one test module per AC); the last entry is the ticket's reachability proof. Every test carries `# covers: <AC-ID>` and `# angle: <angle>`.

```yaml
tests:
- name: test_deployed_instruction_passages_about_workspaces_point_to_the_maker
  file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
  covers:
  - BO-4300f-2-ia
  asserts: Every workspace passage in the deployed agent charters, skills and workflow texts, and in CLAUDE.md,
    names the maker and the get-a-workspace how-to (text is this record's subject, so reading the delivered
    text is the behaviour).
  framework: unittest
  type: unit
  angle: deployed
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_no_deployed_instruction_carries_its_own_workspace_recipe
  file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
  covers:
  - BO-4300f-2-ia
  asserts: None of those texts contains a workspace clone, git worktree add/remove, ln -s / cp of .leafcutter
    or .pre-commit-config.yaml, EnterWorktree, or a manual rm of a workspace.
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_deployed_texts_take_the_ticket_location_only_from_ticket_path_in_worktree
  file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
  covers:
  - BO-4300f-2-ia
  asserts: The deployed worktree-agent charter, and every deployed skill or workflow text that names a
    ticket location from a workspace answer, name ticket_path_in_worktree and contain no ticket_path_new
    or ticket_path_final (delivered text is the subject).
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_howto_workspace_passages_point_to_the_maker
  file: unit_tests/build_orchestration/test_bo_4300f_2_ib.py
  covers:
  - BO-4300f-2-ib
  asserts: Every workspace passage in the delivered how-to guides names the maker and the get-a-workspace
    how-to.
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_no_howto_carries_its_own_workspace_recipe
  file: unit_tests/build_orchestration/test_bo_4300f_2_ib.py
  covers:
  - BO-4300f-2-ib
  asserts: No how-to guide contains its own clone, worktree, link, install or delete steps for a workspace.
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_each_former_way_is_absent_or_relays_the_makers_answer_unchanged
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: In the shared deployed layout, each former script, sub-command, the facts helper's base lookup
    and the recovery re-add is absent, or its answer equals (after normalising timestamps) the maker's
    answer to the equivalent request.
  framework: unittest
  type: behavioral
  angle: deployed
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_no_former_way_makes_finds_or_clears_by_its_own_means
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: Invoking any surviving shim against a temp project creates exactly what the maker creates (a
    marker-bearing clone) and nothing else -- no git worktree registration in the main project.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_no_git_worktree_add_or_remove_outside_the_declared_exemptions
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: Over every tracked file of the repository, including the workspace component's own files, no
    spelling of `git worktree add` or `git worktree remove` appears outside the one declared exemption
    list (the BO-4300f-3 cut-over verb, the one legacy_worktree test helper, and the seven record folders);
    each hit is reported by file and line.
  framework: unittest
  type: unit
  angle: seam
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_census_reports_a_how_to_hit_but_not_the_same_text_in_an_analysis
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: Fed a fixture tree holding the same `git worktree add` instruction in docs/how-to/<file>.md
    and in docs/analysis/<file>.md, the census reports the how-to hit by file and line and does not report
    the analysis; the same text in a component file (e.g. a second helper in the fixture module beside
    the exempt legacy_worktree helper) is also reported.
  framework: unittest
  type: unit
  angle: boundary
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_census_exemption_list_is_one_declared_list_with_reasons_and_folder_entries
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: The census's exemptions come from one declared list in which every entry carries a non-empty
    reason; the record exclusions are exactly the seven folders (analyses, known issues, retrospectives,
    changelogs, architecture decision records, tickets, acceptance criteria) as folder entries, and there
    are no file-level entries other than the cut-over verb and the one legacy_worktree helper.
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_census_excludes_adrs_but_reports_component_docs
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: Fed a fixture tree holding the same `git worktree add` instruction in docs/architecture/adrs/<file>.md
    and in docs/architecture/components/<file>.md, the census reports the component-doc hit by file and
    line and does not report the ADR.
  framework: unittest
  type: unit
  angle: boundary
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_build_refuses_an_implicit_build_into_the_package_repository
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: In a disposable copy of the package repository under the test's temp directory (never the developer's
    own checkout), running that copy's scripts/build.py from its root with no --target-dir exits non-zero
    with a message naming the rule and --target-dir, before any build phase; no .leafcutter/ folder is
    created and the copy's working tree (git status --porcelain --ignored) is unchanged. This is a build.py
    spawn site justified in ticket 14 -- the refusal exits before any phase, and the explicit-target path
    is already proven by the shared deployed layout and the maker's workspace builds, so no full build
    is spawned.
  framework: unittest
  type: behavioral
  angle: failure
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_census_detects_every_spelling_of_the_commands
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: Fed fixture files holding the shell form, the -C form, a Python argv list and a JS template
    literal, the census reports all four; fed the exempt cut-over verb's file it reports none.
  framework: unittest
  type: unit
  angle: failure
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_no_git_dash_c_commit_in_component_files_or_instruction_surfaces
  file: unit_tests/build_orchestration/test_bo_4300f_2.py
  covers:
  - BO-4300f-2
  asserts: No `git -C <path> commit` (shell or argv form) appears in the component's own files or in any
    instruction surface; a fixture file containing it is reported.
  framework: unittest
  type: unit
  angle: criterion
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
- name: test_ticket_14_reachable_from_entry_point
  file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
  covers:
  - BO-4300f-2
  angle: reachability
  surface_invoked: the census test over the real tracked tree, and each former script name invoked as
    a consumer install would (CLI via subprocess)
  asserts: Invoke the production entry point named in surface_invoked (never an import of the function)
    and assert the new behaviour occurs and is consumed.
  implementation_files:
  - scripts/setup_ticket_worktree.py
  - templates/scripts/setup_ticket_worktree.py
  - templates/scripts/worktree_repo_facts.py
  - templates/scripts/git_recovery.py
  - scripts/worktree/check_workspace_setup_permission.py
  - scripts/worktree/README.md
```

## Implementation Notes

### Ticket-specific (harvested from the failed run and the AC records)

- DELETE `scripts/setup_ticket_worktree.py` (tracked drifted copy) and the drift-ENFORCING assertion in `test_fastlane_template_deploy_parity.py`; delete `templates/scripts/setup_ticket_worktree.py` or replace it for at most one release with a shim mapping each sub-command to the maker (removal release in its docstring). `worktree_repo_facts.py` removed (or shimmed) after ticket 11 stops build-feature using it; its four BO-4000 tests re-pointed or removed with their promises re-homed. `git_recovery.py`'s worktree re-add fallback removed. `check_workspace_setup_permission.py`'s own first-match repository search replaced by the maker's resolution (the file stays; ~25 ACD-2100/BO-1500 tests use it). Deploy manifests drop the deleted scripts; the maker's named entries stay.
- CENSUS (f-2): one test module, one declared exclusion list BY FOLDER (docs/analysis/, docs/known-issues/, docs/retrospectives/, changelogs/, tickets/, docs/acceptance-criteria/) plus the two declared exemptions; each hit reported by file and line; a second census for `git -C <path> commit` over the component's files and the instruction surfaces. A 2026-09-28 `git grep` of `git worktree (add|remove)` and argv forms found 58 tracked files outside the excluded folders; they are in files_touched. The census also matches folder-first and template forms, so run it first and get files_touched extended with anything it adds before editing.
- OPEN: `docs/architecture/adrs/` (ADR-006, ADR-018, ADR-039 match the census) is neither in the AC's excluded list nor its explicit in-scope list ('a new record folder is in scope until it is added to the list with its reason'). Ask the user whether ADRs are records of the past; until answered they are NOT in files_touched.
- INSTRUCTIONS (f-2-ia, llm-expert): worktree-agent.md stops reporting `ticket_path_new` and reports the ticket location only from `ticket_path_in_worktree` (same change set as BO-4300a-1-ii); building-epics' direct `git worktree remove` fallback and non-halting pre-drive probe, build-feature-ops-notes' `git worktree add --detach /tmp/base`, ship's `git worktree remove`, quick-fix's two-location lookup, close-worktree/build-backlog/worktree workflow texts. CLAUDE.md: replace 'Worktree pre-commit config (MANDATORY for worktree-based drives)' with 'run the maker', delete the `.security-allowlist` symlink paragraph and the BOTH-copies instruction, rewrite 'Prefer the symlink instead'; 'Land the scaffold commit on origin/main' points at the maker. CLAUDE.md is edited directly (not a template).
- HOW-TOS (f-2-ib, documentation-expert): `drive-epic-manually.md`, `verify-precommit-active.md` and any other how-to page that makes, finds or clears a workspace point at the maker and `docs/how-to/get-a-workspace.md`; no own steps remain.
- ADR-001 'Installed-Layout Path Resolution' names `_resolve_installed_layout()` in `scripts/setup_ticket_worktree.py` as authority; 01's adr-author added a note that it is replaced after BO-4300f-2. Update it when the script goes (requires_adr: true).
- Q6 DECIDED (user, 2026-09-28): `leafcutter-ai/.leafcutter/` (the stale install inside the package repository) must NOT exist. (1) DELETE it from the developer's main checkout (`C:/Users/Hendrik/Code/leafcutter/leafcutter-ai/.leafcutter/` on the reference host) -- it is untracked and gitignored, so this is an operational step: record it in this ticket's Comments with the before/after listing, and never delete the parent workspace's current install (`<workspace>/.leafcutter/`). (2) REFUSAL in `scripts/build.py`: with no explicit `--target-dir`, a build whose target resolves to the package repository itself (derived from the build's own package root, not a hard-coded folder name) exits non-zero BEFORE any phase writes anything, naming the rule and the `--target-dir` remedy. An explicit `--target-dir` is never refused: CI runs `python scripts/build.py --target-dir .` at the package root, `build-self.sh` passes `--target-dir <workspace>`, and the maker passes the workspace explicitly when it builds inside a workspace of the package (BO-4300a-1). Keep the refusal inside the file-size ratchet of `build.py` (a small guard helper beside the existing validation guards). (3) The `.leafcutter/` ignore entry stays -- package workspaces carry their own install inside the clone (decision 2). (4) The refusal test runs a disposable copy of the package under the test's temp dir, never the developer's checkout; it is a build.py spawn site justified here because the refusal exits before any phase (CLAUDE.md 'Tests must not spawn their own build.py'). (5) adr-author records the refusal and the absence of an install copy inside the package repository in ADR-001 (self-hosting boundary), which this ticket already edits.
- CENSUS RECORD FOLDERS (settled by the coordinator 2026-09-28): `docs/architecture/adrs/` is a records-of-the-past folder and is excluded by folder in the one declared list alongside analyses, known issues, retrospectives, changelogs, tickets and acceptance criteria -- seven entries. Every other `docs/architecture/` folder (components/, diagrams/) stays in scope.
- This is the largest ticket of the re-cut (census blast radius ~58 files). If architect-review judges it too big, split the fixture migration (unit_tests/*/test files) into a sibling ticket that keeps BO-4300f-2 and depends on it -- an AC is never split across two tickets.

### AC technical requirements (verbatim from the AC store; shared boilerplate omitted)

**BO-4300f-2-ia**

- Surfaces: templates/agents/*.md (worktree-agent.md's create-only/setup-ticket recipe and its wrong ticket_path_new field; any agent that probes or removes workspaces), templates/skills/*/SKILL.md (feature epic recipe, building-epics' direct `git worktree remove` fallback and non-halting pre-drive probe, build-feature-ops-notes' `git worktree add --detach /tmp/base`, ship's `git worktree remove`, quick-fix's two-location lookup), templates/workflows/*.md (close-worktree.md, build-backlog.md, worktree.md), and the project rules file CLAUDE.md.
- CLAUDE.md (item routed here): replace 'Worktree pre-commit config (MANDATORY for worktree-based drives)' -- its fail-open `ls .pre-commit-config.yaml || ls .leafcutter` check and its symlink-preferred Option A / copy Option B fixes -- with 'run the maker'; delete the '.security-allowlist resolves via the symlink target' latent-hazard paragraph and the BOTH-copies dual-update instruction in 'Security Allowlist -- Use Glob Patterns' (with real install files the hook reads the workspace's own allowlist; decision memo Q2); rewrite the 'Prefer the symlink instead' advice in the feedback_categories section. The 'Land the scaffold commit on origin/main' section stays true (base is origin/main) but points at the maker instead of worktree-agent.
- Every rewritten passage points to the maker and to docs/how-to/get-a-workspace.md; none keeps its own copy, clone, worktree, link, install or delete steps.
- Template edits reach consumers only through the build; the repo's own CLAUDE.md is edited directly (it is not a template).
- TICKET LOCATION (KI-BO-20260925-build-single-ticket-treats-ticket-path-final-as-worktree-path; routed from BO-4300a-1-ii, lands in the SAME change set as it): templates/agents/worktree-agent.md stops parsing and reporting ticket_path_new (a field the set-up script no longer emits) and reports the ticket's working location ONLY from ticket_path_in_worktree of the maker's ok answer; no charter, skill or workflow text describes ticket_path_final or the path a caller passed in as "the ticket inside the workspace".
- Commit spelling (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): no passage this record rewrites spells a commit as `git -C <path> commit`, because the commit-delegation hook matches only the literal "git commit"; commits are delegated to the commit agent per CLAUDE.md, and -C appears only with non-commit verbs.

**BO-4300f-2-ib**

- Surfaces: docs/how-to/drive-epic-manually.md (EnterWorktree with no bootstrap, 'do not use any shell script'), docs/how-to/verify-precommit-active.md (stale claims), and any other docs/how-to page that makes, finds or clears a workspace.
- Each passage directs the reader to the maker and to docs/how-to/get-a-workspace.md; no own steps remain.
- Frontmatter per the project doc conventions (title, description, type, status, created, last_updated, components: [worktree_manager, build_orchestration]); must pass the doc-related pre-commit hooks and be reachable from docs/INDEX.md via the build's doc index.

**BO-4300f-2**

- Delete scripts/setup_ticket_worktree.py (the tracked, drifted copy) and the drift-ENFORCING test (test_fastlane_template_deploy_parity.py's template-must-not-have-the-gate assertion). templates/scripts/setup_ticket_worktree.py is deleted, or for at most one release replaced by a shim that maps each sub-command to the maker (setup-ticket -> ensure --kind ticket, create-only -> feature, create-ac-worktree -> ac, create-fastlane-worktree -> fastlane) and relays the maker's answer unchanged; the shim's removal release is recorded in its own docstring.
- worktree_repo_facts.py's base lookup is removed or shims to the maker; git_recovery.py's worktree re-add fallback is removed; scripts/worktree/check_workspace_setup_permission.py's own first-match repository search is removed in favour of the maker's resolution.
- The build deploy manifest drops entries for deleted scripts; the maker's named entry (BO-4300a-1) stays.
- Tests and docs that exercised the deleted scripts (tests/test_setup_ticket_worktree.py's 41 mock sites) are removed or re-pointed at the maker, never left skipped.
- Q6 (DECIDED user 2026-09-28): leafcutter-ai/.leafcutter/, the stale install inside the package repository, must NOT exist. The ticket deletes it from the developer's main checkout (it is untracked and gitignored, so the deletion is an operational step recorded in the ticket, not a tracked change), and no former way can survive in it.
- Q6 BUILD REFUSAL: scripts/build.py refuses to build into the package repository itself when no explicit --target-dir is given (today an implicit build targets cwd, which is how that copy was made). The refusal happens before any build phase writes anything, exits non-zero and names the rule and the --target-dir remedy. An explicit --target-dir is never refused -- including --target-dir . at the package root, which CI uses, and the explicit workspace target the maker passes when it builds inside a workspace of the package (BO-4300a-1). Recognising "the package repository" derives from the build's own package root, not from a hard-coded folder name. build-self.sh already passes --target-dir and is unaffected.
- The .leafcutter/ ignore entry stays: workspaces of the package carry their own install inside the clone (decision 2), built with an explicit --target-dir. So "must not exist" is enforced by the build refusal and the one-time deletion, not by a test that fails whenever a package clone holds an install.
- REPO-WIDE CENSUS (duplication audit item 10): a test fails when `git worktree add` or `git worktree remove` appears anywhere in the package repository's tracked files, INCLUDING the workspace component's own files (the maker, the resolver module, the fixture module, this family's tests) -- the component is not exempt as a whole. Every spelling counts: shell text, argv lists (["git", "worktree", "add"] and the -C form), template literals and prose instructions. The ONLY exemptions are: (1) the legacy cut-over verb of BO-4300f-3; (2) the single legacy_worktree test helper its tests use (delivered in the BO-4300f-4 fixture module) -- both exempted as those specific sites, not as the files or folders around them; and (3) the record folders of decision 2 below. All three live in ONE declared exemption list in the test, each entry with its reason; each failure names the file and line.
- Census exclusion of historical records (DECIDED, user 2026-09-27): records of the past are excluded BY FOLDER, in the same one declared list, never file by file: docs/analysis/ (analyses), docs/known-issues/ (known issues), docs/retrospectives/ (retrospectives), changelogs/ (changelogs), docs/architecture/adrs/ (architecture decision records -- settled by the coordinator 2026-09-28: an ADR records a past decision and may quote the old commands as context), tickets/ (tickets) and docs/acceptance-criteria/ (acceptance criteria) -- seven folders. Verified 2026-09-25: about 94 of the 157 tracked files that mention the commands are in the first six. Everything that instructs or executes stays in scope -- templates/, scripts/, config/, unit_tests/, tests/, docs/how-to/, docs/reference/, docs/agents/, docs/architecture/components/ (and every docs/architecture/ folder other than adrs/), every README.md and CLAUDE.md -- so a new record folder is in scope until it is added to the list with its reason.
- Blast radius (verified 2026-09-25): besides the scripts this record already deletes, the census goes red on ~33 test files under unit_tests/ and tests/ that build git worktrees as fixtures, and on templates/skills, templates/agents, templates/workflows and templates/workflows-js sites. Making it green is in scope: test fixtures move to the BO-4300f-4 helper or become maker-made clones; instruction sites are rewritten under BO-4300a-1-ia, BO-4300a-1-ib, BO-4300f-2-ia and BO-4300f-2-ib.
- Commit spelling census (KI-CG-20260925-commit-delegation-hook-misses-git-dash-c): in the same test module, a second census fails when `git -C <path> commit` (or its argv form) appears in the component's own files (maker, resolver module, fixture module, this family's tests) or in any instruction surface (templates/agents, templates/skills, templates/commands, templates/workflows, templates/workflows-js, docs/how-to, CLAUDE.md). Python test fixtures elsewhere that commit through a subprocess are out of scope (the delegation hook only sees agent shell commands).

## Agent Contracts

### python-coder

- [x] AC-3: BO-4300f-2 -- The former ways of making a workspace are gone from what an install delivers <!-- signed: python-coder -->

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### llm-expert

- [x] AC-1: BO-4300f-2-ia -- Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces <!-- signed: llm-expert -->

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [x] AC-1: red tests for BO-4300f-2-ia per `## Test Requirements` <!-- signed: test-writer -->
- [x] AC-2: red tests for BO-4300f-2-ib per `## Test Requirements` <!-- signed: test-writer -->
- [x] AC-3: red tests for BO-4300f-2 per `## Test Requirements` <!-- signed: test-writer -->

**Delivered files (test-writer):** `unit_tests/build_orchestration/test_bo_4300f_2.py`, `test_bo_4300f_2_ia.py`, `test_bo_4300f_2_ib.py`, shared support `_bo_4300f_2_fixtures.py` (new; holds the one declared exemption list and the scanners).

**Delivers to:** python-coder, llm-expert (red baseline).

### documentation-expert

- [x] AC-2: how-to | docs/how-to/drive-epic-manually.md | points at the maker and get-a-workspace.md <!-- signed: documentation-expert -->
- [x] AC-2: how-to | docs/how-to/verify-precommit-active.md | stale claims removed; points at the maker <!-- signed: documentation-expert -->

### Expects From

- **BO-4300f-2-ia <- BO-4300a-3** (13_TICKET-20260928-BO-4300-docs-and-diagrams.md): docs/how-to/get-a-workspace.md exists as the single replacement page.
- **BO-4300f-2-ib <- BO-4300a-3** (13_TICKET-20260928-BO-4300-docs-and-diagrams.md): docs/how-to/get-a-workspace.md exists as the single replacement page.
- **BO-4300f-2 <- BO-4300f-1** (11_TICKET-20260928-BO-4300-workflow-routes.md): Every caller migrated to the maker before the former ways are removed.

### Delivers To

- none

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_bo_4300f_2_ia.py:test_deployed_instruction_passages_about_workspaces_point_to_the_maker; test_bo_4300f_2_ia.py:test_no_deployed_instruction_carries_its_own_workspace_recipe; test_bo_4300f_2_ia.py:test_deployed_texts_take_the_ticket_location_only_from_ticket_path_in_worktree | Rewrote every workspace passage in templates/agents, skills, workflows, commands and CLAUDE.md to name the maker and get-a-workspace.md; no own recipe remains |  covered |
| AC-2 | test_bo_4300f_2_ib.py:test_howto_workspace_passages_point_to_the_maker; test_bo_4300f_2_ib.py:test_no_howto_carries_its_own_workspace_recipe | Rewrote workspace passages in docs/how-to (drive-epic-manually, verify-precommit-active, finalize-feature, fast-lane-build, others) to name the maker and get-a-workspace.md; removed EnterWorktree steps |  covered |
| AC-3 | test_bo_4300f_2.py:test_each_former_way_is_absent_or_relays_the_makers_answer_unchanged; test_bo_4300f_2.py:test_no_git_worktree_add_or_remove_outside_the_declared_exemptions; test_bo_4300f_2.py:test_build_refuses_an_implicit_build_into_the_package_repository; test_bo_4300f_2_ia.py:test_ticket_14_reachable_from_entry_point | |  covered |

## Risk & Safety

- Touches money? No.
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [x] architect-review — 2026-10-13 09:00
- [x] adr-author — 2026-10-13 08:38
- [x] test-writer — 2026-10-13 09:05
- [x] python-coder — 2026-10-14 08:00
- [x] llm-expert — 2026-10-14 08:50
- [x] test-runner — 2026-10-14 11:00
- [x] documentation-expert — 2026-10-14 10:15
- [x] pr-reviewer — 2026-10-14 12:00
- [x] ac-validator — 2026-10-14 12:30
- [x] ac-fulfillment-gate — 2026-10-14 13:00
- [x] documentation-verifier — 2026-10-14 13:10
- [x] commit — 2026-10-14 14:00

## Comments

### 2026-10-14 12:30 — ac-validator (status: ok)
feedback-id: fb_2026-10-14_5730a0cb

All 3 ACs covered; store alignment script rc=0; 15 tests in test_bo_4300f_2*.py pass (AC_ENFORCE_STRICT=1).

AC-1 covered: implementation: templates/agents, skills, workflows, CLAUDE.md rewritten (staged diff); docs/how-to/get-a-workspace.md exists. test: test_no_deployed_instruction_carries_its_own_workspace_recipe (unit_tests/build_orchestration/test_bo_4300f_2_ia.py:56)
AC-2 covered: implementation: docs/how-to/drive-epic-manually.md, verify-precommit-active.md (staged diff). test: test_no_howto_carries_its_own_workspace_recipe (unit_tests/build_orchestration/test_bo_4300f_2_ib.py:42)
AC-3 covered: implementation: scripts/setup_ticket_worktree.py, templates/scripts/setup_ticket_worktree.py, templates/scripts/git_recovery.py (staged diff). test: test_no_git_worktree_add_or_remove_outside_the_declared_exemptions (unit_tests/build_orchestration/test_bo_4300f_2.py:173)

### 2026-10-14 12:00 — pr-reviewer (status: ok)
feedback-id: fb_2026-10-14_f4a7ea59
Reviewed the working diff vs HEAD (111 files, mostly deletions of the former set-up script and its tests). The three ticket test modules plus tests/test_git_recovery.py pass (108 passed, AC_ENFORCE_STRICT=1). No contract-mismatch, instruction-less-dispatch or topology-only findings. High: 0.
[M-1] Stale pointers to the retired setup_ticket_worktree.py remain in live docs: docs/how-to/verify-precommit-active.md:32,179; docs/architecture/components/{ticket-lifecycle.md:27,34, template-compiler.md:39, worktree-quality-gate-guard.md:46, ac-driven-dev.md:31,38}; agent_delivery_workflows.md:482,1844,2021. Not a recipe, so the census passes, but they name a script an install no longer delivers.
Low (suppressed): .security-allowlist:115 entry for the deleted unit_tests/test_setup_ticket_worktree.py; .github/test_durations.json stale keys; code comments in build_phases*.py and ci.yml:612.
Escalation: not escalated (1 medium, threshold > 3).

### 2026-10-14 11:00 — test-runner (status: ok)
feedback-id: fb_2026-10-14_712f3be1
completion_manifest:
  test_suite_executed: true
  all_tests_passing:
    result: false
    reason: "29 failures in 8 files (test_ge120c1i_*, test_ge_120e_1, test_acd_2100a_1/_4/_5, test_acd_2100c_2/_3/_3_i) - the IDENTICAL 29 fail on a clean detached worktree at base HEAD cc3c85e, so none are introduced by this ticket (Windows-local/stub-harness failures)."
    remediation: "Trust CI for those files; no change attributable to BO-4300-14."
  failure_report_structured: true
AC_ENFORCE_STRICT=1 pytest over the ticket's existing touched test files plus test_bo_4300f_2.py, _ia.py, _ib.py: 244 passed, 29 failed. The three red-baseline tests (4300f_2 worktree-add/-C commit census, _ia reachability) now PASS. Several listed test paths no longer exist (tests/test_setup_ticket_worktree.py, unit_tests/test_setup_ticket_worktree.py, test_fastlane_*, test_bo2400f_13*/3_*) - retired with the old scripts, as intended.

### 2026-10-14 10:15 — documentation-expert (status: ok)
feedback-id: fb_2026-10-14_a27e72e6
completion_manifest:
  doc_written: true
  cross_links_added: true
  diataxis_genre_correct: true
Cleared every docs census hit (README.md, docs/agent-registry.md, agent card, worktree-agent reference, agent_delivery_workflows.md, plan-feature-layout reference) and rewrote the how-to workspace passages (drive-epic-manually Steps 2-4 and the `-C commit` recipe, verify-precommit-active, configure-workflow-allowlist, finalize-feature, fast-lane-build, others) to name the workspace maker and get-a-workspace.md. AC_ENFORCE_STRICT=1 pytest on test_bo_4300f_2.py, _ia.py, _ib.py: 15 passed. The ~35 other failures in test-runner's handoff (item B) are python-coder scope and untouched.

_(Append-only log -- leave blank when authoring.)_
### 2026-10-13 08:38 — adr-author (status: ok)
feedback-id: fb_2026-10-13_b927e3f5
completion_manifest:
  adr_file_created: true
  all_sections_present: true
  status_set: true
ADR-001 is amended in place, as Implementation Notes (ADR-001 update; Q6 point 5) direct, so no new ADR number was allocated: `docs/architecture/adrs/ADR-001-self-hosting-boundary.md` gains "Amendment 1 — 2026-10-13" (Status Proposed), with a Status table, Why, Decision AM1.1–AM1.3, Consequences (Positive/Negative/Operational) and Alternatives. AM1.1 makes the Installed-Layout section a non-binding record; resolution now follows ADR-018 A1.8 (`workspace_root.py`) and A1.9–A1.10 (`worktree_layout.py`). AM1.2 says a developer's package checkout holds no install, `.gitignore` keeps `.leafcutter/`, and the one-time deletion (still pending; `leafcutter-ai/.leafcutter/` exists and still holds `_resolve_installed_layout`, verified 08:37) must not touch `<workspace>/.leafcutter/`. AM1.3 makes `build.py` refuse an implicit build when cwd is the package root or inside it, checked straight after argument parsing, in every mode, with the root derived from `__file__` and never refusing an explicit `--target-dir`. Two choices that go beyond the literal Q6 text and need architect-review's check: "inside it" (the ignore entry hides a copy at any depth) and "every mode" (Q6 has no mode exception). Scope finding for architect-review / python-coder: after AM1.3, package-root `python scripts/build.py` instructions OUTSIDE files_touched become stale. They are docs/how-to/creating-a-claude-code-hook.md, creating-a-skill.md, creating-an-agent-template.md, deprecating-or-removing-artifacts.md, docs/reference/agent-template-frontmatter.md, templates/agents/it-po.md and the remedy line in templates/scripts/commit_guardian/check_build_drift.py:407. Also, unit_tests/test_build_guard_real_package.py::test_main_does_not_call_tracked_source_guard_under_validate_only calls `build.main(["--validate-only"])` without a target and would pass vacuously. Either extend files_touched or open a follow-up ticket. Handoff written to `.pending/adr_handoff.json` (adr_id ADR-001). doc-frontmatter, doc-length, doc-links, adr-cross-reference, adr-coverage, description-field and the transform hooks all pass on the ADR (no warnings printed). The build_pipeline detail_ref `docs/build-pipeline.md` still does not mention ADR-001; this is an existing gap, and the file is not in files_touched.

### 2026-10-13 09:00 — architect-review (status: ok)
feedback-id: fb_2026-10-13_8ccc616f
Classification: LARGE (opus-tier). Always-large trigger fired: has_adr_contract_change=true (ADR-001 amended in place, Amendment 1); also >5 files (~80), 3 components (worktree_manager, build_pipeline, skills_system), cross-package. requires_adr: true (already satisfied by adr-author; no new ADR, suggested_adr null). Diagrams: none (retirement and rewrite, no new boundary). requires_documentation: [how_to, reference, architecture].
Note: research-agent and architect-review-deep could not be spawned (no Agent tool in this run); blast radius taken from the ticket's own 2026-09-28 census and a direct check. Flagged for the supervisor.
Design concerns: (1) AM1.3 build.py refusal goes beyond Q6 text ("inside the package root", "every mode"); acceptable but tests must cover explicit --target-dir . and workspace targets, and the guard must stay inside build.py's file-size ratchet (2223 lines). (2) Census must include its own test module's literals without self-matching: express the patterns by construction, not as literal text, and keep one exemption list of 2 sites + 7 folders. (3) Shim-vs-delete: prefer delete over a one-release shim to keep one way; a shim needs a removal release in its docstring and must relay the maker answer unchanged. (4) Commit-spelling census (git -C ... commit) is a second census in the same module.
Acceptance adjustments: (a) extend files_touched with package-root build.py instructions made stale by AM1.3: docs/how-to/creating-a-claude-code-hook.md, creating-a-skill.md, creating-an-agent-template.md, deprecating-or-removing-artifacts.md, docs/reference/agent-template-frontmatter.md, templates/agents/it-po.md, templates/scripts/commit_guardian/check_build_drift.py (remedy line ~407), and unit_tests/test_build_guard_real_package.py (vacuous --validate-only call). (b) Run the census first and extend files_touched with whatever it adds before editing. (c) Operational deletion of leafcutter-ai/.leafcutter/ in the main checkout is still to be done and recorded with before/after listing in Comments; it is not a tracked change and never touches <workspace>/.leafcutter/. (d) ticket_path_new/ticket_path_final must not appear in delivered text (AC-1 third test).
Split recommendation: the ticket is the largest of the re-cut. Sequence work in two lanes inside this ticket (lane 1: scripts/build/templates/instruction text + census; lane 2: ~33 fixture test files migrated to the BO-4300f-4 helper or maker clones). If lane 2 stalls, split the fixture migration into a sibling ticket that depends on 4300f-4 and keeps BO-4300f-2 (an AC is never split across tickets). Not split now.

### 2026-10-13 09:05 — test-writer (status: ok)
feedback-id: fb_2026-10-13_4bdaec80
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "every tracked file's text (git ls-files incl. untracked-not-ignored) and the DEPLOYED layout's charters/skills/commands/workflows"
    consuming_side: "the census scanner against the one declared exemption list (test_bo_4300f_2.py), and the passage/recipe scanners in _bo_4300f_2_fixtures.py"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "the census test over the real tracked tree, and each former script name invoked as a consumer install would (CLI via subprocess)"
Four files written. Run (AC_ENFORCE_STRICT=1, 152s): 11 failed, 4 passed. Red (assertion kind): both former-way proofs (old setup script answers differently / makes a registration), real-tree census (207 hits in 66 files), `-C ... commit` census (3 hits), build-refusal (implicit build ran, no `--target-dir` message), -ia x3 (63 passages lack the pointer, 17 recipe hits, charter still names ticket_path_new), -ib x2 (16 passages, EnterWorktree in drive-epic-manually.md), reachability (census CLI exit 1). Green by design (self-contained census mechanics: fixture trees, ADR vs component, four spellings, exemption list) so the real-tree test cannot be satisfied by weakening the census; flagged "passes immediately". Q1 wrong versions now caught: census reading only tracked-not-untracked files (new files are scanned), exempting a folder around the helper file instead of the file, excluding adrs/ but also components/, matching only the shell spelling; a shim that answers but registers a linked workspace; a refusal that still creates .leafcutter/. Notes for python-coder: (1) SHIM CONTRACT is assumed in the docstring of test_bo_4300f_2.py (`<sub-command> <slug> --repo-root P` -> `ensure --kind K ...`); deleting the script satisfies it. (2) A surviving worktree_repo_facts.py must name the maker and run no subprocess. (3) Exemptions are templates/scripts/worktree_migrate.py and unit_tests/build_orchestration/_workspace_maker_builders.py. (4) AM1.3 refusal: control row expects `build.py --validate-only --target-dir .` to exit 0 in the package copy. (5) The test session guard (_developer_repo_guard) can error at teardown when other sessions touch the shared repository; that is environmental. (6) Operational incident, repaired: an early draft of the build-refusal fixture copied the `.git` gitlink file into the temp copy and staged the whole copy into this workspace's index; the canary hook rejected the commit, `git reset -q` restored the index, no commit or tree change resulted; the fixture now never copies `.git` and pins GIT_DIR/GIT_WORK_TREE.
red_baseline:
  - test_name: test_each_former_way_is_absent_or_relays_the_makers_answer_unchanged
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['setup-ticket: no single JSON answer (exit ...)']"
  - test_name: test_no_former_way_makes_finds_or_clears_by_its_own_means
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['setup-ticket: no marker-bearing clone at ...']"
  - test_name: test_no_git_worktree_add_or_remove_outside_the_declared_exemptions
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['README.md:64', 'config/skills_config.sch...']"
  - test_name: test_no_git_dash_c_commit_in_component_files_or_instruction_surfaces
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['docs/how-to/drive-epic-manually.md:203', ... 'test_bo_4300c_3_i.py:94']"
  - test_name: test_build_refuses_an_implicit_build_into_the_package_repository
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: '--target-dir' not found in 'Loading config for target: ...\\pkg ...'"
  - test_name: test_deployed_instruction_passages_about_workspaces_point_to_the_maker
    file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['.claude/agents/documentation-verifier.md:113', ...]"
  - test_name: test_no_deployed_instruction_carries_its_own_workspace_recipe
    file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['.claude/agents/epic-supervisor.md:537 (old-way add/remove)', ...]"
  - test_name: test_deployed_texts_take_the_ticket_location_only_from_ticket_path_in_worktree
    file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
    kind: assertion
    error: "AssertionError: 'ticket_path_in_worktree' not found in worktree-agent charter"
  - test_name: test_ticket_14_reachable_from_entry_point
    file: unit_tests/build_orchestration/test_bo_4300f_2_ia.py
    kind: assertion
    error: "AssertionError: 0 != 1 : census hits:"
  - test_name: test_howto_workspace_passages_point_to_the_maker
    file: unit_tests/build_orchestration/test_bo_4300f_2_ib.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['docs/how-to/configure-workflow-allowlist...', ...]"
  - test_name: test_no_howto_carries_its_own_workspace_recipe
    file: unit_tests/build_orchestration/test_bo_4300f_2_ib.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['docs/how-to/drive-epic-manually.md:87 (EnterWorktree)', ...]"

### 2026-10-13 13:30 — test-writer (status: ok)
feedback-id: fb_2026-10-13_8d352ce5
(classification: test_drift) Re-dispatched by python-coder's handoff. Production is correct; the tests below spelled the old way or exercised the deleted script / lookups. No production file was touched.
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "the maker's real deployed answers (run_maker) and real linked checkouts made by the exempt helper"
    consuming_side: "build-feature.js's top-level body (BO-4000c re-pointed case) and the census over every tracked test file"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "python -m unit_tests.build_orchestration.test_bo_4300f_2 --census, and the deployed worktree.py via subprocess (CLI)"
Test migration done. Test-side census is now empty (`--census` lists no tests/ or unit_tests/ file). Remaining red in test_bo_4300f_2*.py (7 tests) is docs/templates text only: llm-expert (templates/agents, skills, workflows) and documentation-expert (README.md, docs/**); the `-C ... commit` census is down to docs/how-to/drive-epic-manually.md:203.

Exempt helper: `link_checkout` / `unlink_checkout` added to `unit_tests/build_orchestration/_workspace_maker_builders.py` (the declared exempt file) and re-exported from `_workspace_maker_fixtures.py`; every fixture that needs a real linked checkout calls these instead of spelling the old command. Text needles use `OLD_WAY_ADD_TEXT` / `OLD_WAY_REMOVE_TEXT` (assembled from pieces in `_bo_4300f_2_fixtures.py`).

Deleted (promises re-homed to the maker's own BO-4300 proofs; the old subcommands no longer exist):
- tests/test_setup_ticket_worktree.py, unit_tests/test_setup_ticket_worktree.py, unit_tests/setup/test_setup_ticket_worktree.py
- unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py, test_fastlane_worktree_mode.py, test_bootstrap_child_stdout_to_stderr.py, test_bo_4100d_4.py
- unit_tests/build_orchestration/test_bo2400f_13_*.py (13, 13i, 13ii, 13iii, 13iv), test_bo2400f_3_reconnect_stale_main_behavioral.py, _bo2400f13_fixtures.py
- unit_tests/ac_driven_dev/test_acd_2100a_2.py, _2_i.py, _2_ii.py
Note for the AC owner: ACs BO-2400f-3, BO-2400f-13*, BO-4100d-4 and ACD-2100a-2* lose their tests with the script; they need superseding in the AC store (outside this phase).

Edited:
- tests/test_git_recovery.py: dropped TestFreshWorktreeFallback, the two real-linked-worktree tests, and the detect_poisoned_linked_worktrees patch (93 pass).
- BO-4000 family: test_bo4000_worktree_reuse_and_naming.py (facts assertions replaced by .git-pointer facts of the real checkout), test_bo4000b (real-repo branch-standing class removed), test_bo4000c (real-repo case re-pointed to the REAL maker: same slug same place from project and from a maker-made workspace; plain-directory occupant refused OCCUPIED, content untouched), test_bo4000f (facts/base classes removed; driver-anchoring and real-maker-answer tests kept). 4000d needed no change.
- test_finalize_pre_merge_safety_gate.py: FIN-100a-1 now asserts Step 0 runs through mainTestRun whose first act is the maker's scratch ensure (was failing at HEAD).
- test_bo_4300f_4.py (tracked-source-copy case uses scripts/build.py), test_bp_900g_6_paths.py (expects scripts/worktree.py), test_bo_4300c_3_i.py (commit via cwd, not -C), quick-fix / bo_1500f_1 / bo_4300_docs / bo_4300f_1 / bo_4300a_1_ia fixtures (needles), acd_2100a_1/3/4/5, c_2/c_3/c_3_i, portability ge_120e_1(_i)/ge120c1i/_bp900h4, commit_guardian pathbase, tq_600a_9, inf_700a_5_i + _inf700a5iii_scratch, bo_4300d_3_i, bo_4300f_4_i, and prose in 22 other test files (comment/docstring wording only).

Verification (AC_ENFORCE_STRICT=1, Windows): all edited files parse and ruff clean. Same failures before and after (checked against a clean HEAD worktree, so not caused by this ticket): test_acd_2100a_1/4/5, c_2/c_3/c_3_i (23+), test_plan_feature_pt_phase (28), test_bo_100e_4_continue_past_halt (11), test_inf_700a_5_i/_iii (fcntl, encoding), test_ge_120e_1 (2) and test_ge120c1i (1).
Wrong versions the migrated tests still catch: a reintroduced old-way line in any test file (census), a maker that names a different place from a linked workspace (BO-4000c case), an occupant dir that is reused or altered (BO-4000c case).
red_baseline:
  - test_name: test_no_git_worktree_add_or_remove_outside_the_declared_exemptions
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['README.md:64', 'docs/agent-registry.md:36', ... 'templates/workflows/worktree.md:2'] (21 hits, 0 in tests)"
  - test_name: test_no_git_dash_c_commit_in_component_files_or_instruction_surfaces
    file: unit_tests/build_orchestration/test_bo_4300f_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [] != ['docs/how-to/drive-epic-manually.md:203']"

### 2026-10-14 08:00 — python-coder (status: ok)
feedback-id: fb_2026-10-14_a875f765
Production side of BO-4300f-2 complete (see the 2026-10-13 12:00 handoff; test-writer migrated tests). Verified now: former-way absence/relay, no-own-means, build-refusal and census-mechanics tests pass (7 passed; the real-tree census is the only xfail, text-only hits). The one teardown ERROR on the build-refusal test is the developer-repo guard seeing a concurrent origin fetch ref (environmental).
Remaining census hits (21, all docs/templates text, not python-coder scope): README.md, docs/agent-registry.md, docs/agents/*, docs/architecture/agent_delivery_workflows.md, docs/reference/plan-feature-layout-and-startup-checks.md, templates/agents/epic-supervisor.md, templates/skills/{build-feature-ops-notes,building-epics,ship}, templates/workflows/{close-worktree,worktree}.md, plus drive-epic-manually.md:203 (-C commit). Owners: llm-expert, documentation-expert.
Operational Q6 step still pending: delete leafcutter-ai/.leafcutter/ in the main checkout (holds paused_runs modified 2026-10-13); needs user confirmation.
red_baseline_results: test_no_git_worktree_add_or_remove_outside_the_declared_exemptions: still red (docs/templates text); test_no_git_dash_c_commit_...: still red (drive-epic-manually.md:203); test_ticket_14_reachable_from_entry_point: still red (census).

### 2026-10-14 08:50 — llm-expert (status: ok)
feedback-id: fb_2026-10-14_ccf8a91d
completion_manifest:
  template_written: true
  prompt_quality_checklist_passed: true
  convention_violations_resolved: true
AC BO-4300f-2-ia done: every workspace passage in the instruction templates and CLAUDE.md now names the maker (`scripts/worktree.py`) and `docs/how-to/get-a-workspace.md`, with no own clone, add/remove, link/copy or manual-delete steps. Rewritten: worktree-agent charter (maker calls only; ticket location only from `ticket_path_in_worktree`), close-worktree (maker `locate`/`remove`, UNSENT_WORK handling), worktree and build-backlog and pick-next-ticket workflows, epic-supervisor, documentation-verifier (heading), building-epics (clearing fallback now the maker; the pre-drive hook probe now halts with no override), build-feature-ops-notes (KI-1/3/6), ship, quick-fix, plan-feature, build-single-ticket, the build-feature/finalize-feature/quick-fix commands, and CLAUDE.md (pre-commit section -> run the maker; symlink and both-copies allowlist advice removed; scaffold section points at the maker). Extended beyond files_touched (census/passage scan found them): templates/agents/documentation-verifier.md, templates/skills/build-single-ticket/SKILL.md, templates/workflows/pick-next-ticket.md, templates/commands/{build-feature,finalize-feature,quick-fix}.md. Verified: test_bo_4300f_2_ia.py 3 passed (the 4th, reachability, still waits on docs/ census hits); census now lists only README.md and docs/** (documentation-expert). Remaining census hits: README.md:64, docs/agent-registry.md:36, docs/agents/cards/workflow-architect.card.md:142, docs/agents/utility/worktree-agent.md:35,92, docs/architecture/agent_delivery_workflows.md:480,496,497,1672, docs/reference/plan-feature-layout-and-startup-checks.md:93. Note for documentation-expert: docs/agents/utility/worktree-agent.md mirrors the charter I just rewrote. A teardown ERROR from the developer-repo guard (concurrent registration change) appears on every run here and is environmental.

### 2026-10-14 09:30 — test-runner (status: handoff)
feedback-id: fb_2026-10-14_c8c096e9
Ran the 36 touched/new test files (AC_ENFORCE_STRICT=1, pytest): 273 passed, 40 failed, 1 error (426s). NOT signed off (suite red).
A. Ticket-owned, awaiting docs (-> documentation-expert): test_bo_4300f_2.py (2: census `git -C commit` hit docs/how-to/drive-epic-manually.md:203; `git worktree add/remove` hits README.md:64, docs/agent-registry.md:36, docs/agents/cards/workflow-architect.card.md:142, docs/agents/utility/worktree-agent.md, docs/architecture/agent_delivery_workflows.md, docs/reference/plan-feature-layout-and-startup-checks.md:93), test_bo_4300f_2_ia.py::test_ticket_14_reachable_from_entry_point (census nonzero), test_bo_4300f_2_ib.py (2: docs/how-to/configure-workflow-allowlist*, drive-epic-manually.md:87 carry own recipe / do not point to the maker).
B. Likely regressions from the retired setup_ticket_worktree.py / workflow changes (-> python-coder to confirm vs a base worktree; some may be Windows-local traps): workflows/test_acd_2100a_1, 2100a_4, 2100a_5, 2100c_2, 2100c_3, 2100c_3_i (no 'worktree-setup' agent() dispatch captured; pause-record tests), workflows/test_inf_700a_5_i_finalize_teardown (5), portability/test_ge_120e_1 (2: TypeError None + str at :529; check_contract_shrinking silent on git failure), portability/test_ge120c1i_setup_failure_reporting (1), workflows/test_quick_fix_worktree_invariant (1 ERROR in developer-repo guard teardown, noted environmental by llm-expert).
Rerun: AC_ENFORCE_STRICT=1 python -m pytest unit_tests/build_orchestration/test_bo_4300f_2.py unit_tests/build_orchestration/test_bo_4300f_2_ia.py unit_tests/build_orchestration/test_bo_4300f_2_ib.py -q

## Escalation

Branch: opus
Reason: has_adr_contract_change=true (ADR-001 amendment) is an always-large trigger; ~80 files across 3 components also exceed the thresholds. Deep review not spawned (tool unavailable); analysis done inline.

### 2026-10-13 12:00 — python-coder (status: handoff)
feedback-id: fb_2026-10-14_266d9f6b

Production side of BO-4300f-2 done; handing the test migration to test-writer (python-coder may not edit tests).

Done (all staged, ruff clean):
- Deleted `scripts/setup_ticket_worktree.py` and `templates/scripts/setup_ticket_worktree.py` (absent is conforming; no shim). Deploy manifests are glob-based, nothing named them.
- `templates/scripts/worktree_repo_facts.py` reduced to the `dirty` subcommand only (build-feature.js still uses it); the `facts`/`base`/`branch-standing` lookups are gone; it runs git through the maker's `worktree_git.run_git` (new optional `encoding` param) and has no subprocess of its own.
- `templates/scripts/git_recovery.py`: removed `detect_poisoned_linked_worktrees`, `_make_fresh_worktree_fn` and plan step (d).
- `scripts/worktree/check_workspace_setup_permission.py`: own git/child/sibling search replaced by `workspace_root.resolve` (loaded by path; deployed and source layouts).
- Q6 refusal: new `scripts/build_target_guard.py`; `scripts/build.py` calls it before its other imports (so no bytecode or phase output is written). Explicit `--target-dir` never refused.
- Comment/text sites: fast-lane-ship.js, quick-fix.js, plan-feature.js, finalize-feature.js (the `-C ... commit` closure line), sweep_processes.py, config/skills_config.schema.json, scripts/worktree/README.md, docs/reference/skills-config-fields.md, build_phases_script_deploy_standalone.py.
- `templates/agents/worktree-agent.md` create/remove actions rewritten to call the maker (needed so the build's reference guard passes); llm-expert still owns the rest of the charter (frontmatter bootstrap behaviour, ticket_path_in_worktree wording check).

Green now: test_each_former_way..., test_no_former_way..., test_build_refuses_an_implicit_build_into_the_package_repository, census mechanics tests.
Still red (not python-coder scope): census over the real tree (156 hits, 55 files; run `python -m unit_tests.build_orchestration.test_bo_4300f_2 --census`), -C commit census (docs/how-to/drive-epic-manually.md:203 documentation-expert; `unit_tests/build_orchestration/test_bo_4300c_3_i.py:94` test-writer), and the three llm-expert / two documentation-expert instruction tests (test_bo_4300f_2_ia / _ib).

Operational step NOT done (Q6 deletion of `leafcutter-ai/.leafcutter/` in the developer's main checkout): it holds `paused_runs/` modified today 06:12 and the checkout's live hook config; deleting it is destructive and outside this workspace. Listing before: .agents agents commands config debugging gemini hooks paused_runs pre-commit-config.yaml scripts settings.json skills workflows. The user should confirm no paused run is needed, then delete it.

test-writer tasks (tests exercised the deleted scripts / functions or spell the old way; migrate to the maker or remove WITH their promises re-homed, never skip; dict >5 keys or table >3 rows go to tests/fixtures JSON):
- Delete `tests/test_setup_ticket_worktree.py`, `unit_tests/test_setup_ticket_worktree.py`, `unit_tests/setup/test_setup_ticket_worktree.py`, and the drift-enforcing assertion in `unit_tests/build_orchestration/test_fastlane_template_deploy_parity.py`.
- `tests/test_git_recovery.py`: drop TestFreshWorktreeFallback and the two real-linked-worktree behavioral tests; remove the `detect_poisoned_linked_worktrees` patches (~line 2474).
- Re-point or remove the worktree_repo_facts facts/base/branch-standing tests: unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py, test_bo4000b_branch_staleness_decision.py, test_bo4000c_start_location_and_occupancy.py, test_bo4000d_facts_envelope_depth.py, test_bo4000f_repository_reference_anchor.py (its branch-standing cases).
- `unit_tests/workflows/test_acd_2100a_1.py` (and a_3/a_4/a_5, c_2, c_3, c_3_i): plan-feature.js now calls `worktree.py ensure --kind ac`; fixtures spell the old way.
- Census hits in test fixtures (move to the BO-4300f-4 helper or maker-made clones); files with a hit:
- tests/test_git_recovery.py
- tests/test_setup_ticket_worktree.py
- tests/test_sweep_processes.py
- unit_tests/ac_driven_dev/test_acd_2100a_2_ii.py
- unit_tests/build_orchestration/_bo2400f13_fixtures.py
- unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
- unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
- unit_tests/build_orchestration/test_bo2400f_13ii_foreign_occupant.py
- unit_tests/build_orchestration/test_bo2400f_13iii_refusal_is_inert.py
- unit_tests/build_orchestration/test_bo2400f_13iv_free_location_proceeds.py
- unit_tests/build_orchestration/test_bo2400f_3_reconnect_stale_main_behavioral.py
- unit_tests/build_orchestration/test_bo_4300_docs.py
- unit_tests/build_orchestration/test_bo_4300c_3_i.py
- unit_tests/build_orchestration/test_bo_4300d_3_i.py
- unit_tests/build_orchestration/test_bo_4300f_1.py
- unit_tests/build_orchestration/test_bo_4300f_3.py
- unit_tests/build_orchestration/test_bo_4300f_4_i.py
- unit_tests/build_orchestration/test_fastlane_worktree_mode.py
- unit_tests/commit_guardian/test_check_doc_frontmatter_worktree_pathbase.py
- unit_tests/feedback/test_submit_feedback_worktree_resolution.py
- unit_tests/portability/_bp900h4_layout_helpers.py
- unit_tests/portability/_deployed_check_harness.py
- unit_tests/portability/test_bp_900h_4_i.py
- unit_tests/portability/test_ge120c1i_setup_failure_reporting.py
- unit_tests/portability/test_ge_120e_1.py
- unit_tests/portability/test_ge_120e_1_i.py
- unit_tests/portability/test_ge_120e_4.py
- unit_tests/suite_performance/test_tq_600a_9.py
- unit_tests/test_setup_ticket_worktree.py
- unit_tests/workflows/_inf700a5iii_scratch.py
- unit_tests/workflows/test_acd_2100a_1.py
- unit_tests/workflows/test_acd_2100a_3.py
- unit_tests/workflows/test_acd_2100a_4.py
- unit_tests/workflows/test_acd_2100a_5.py
- unit_tests/workflows/test_acd_2100c_2.py
- unit_tests/workflows/test_acd_2100c_3.py
- unit_tests/workflows/test_acd_2100c_3_i.py
- unit_tests/workflows/test_bo4000_worktree_reuse_and_naming.py
- unit_tests/workflows/test_bo4000c_start_location_and_occupancy.py
- unit_tests/workflows/test_bo4000f_repository_reference_anchor.py
- unit_tests/workflows/test_bo_1500f_1.py
- unit_tests/workflows/test_finalize_pre_merge_safety_gate.py
- unit_tests/workflows/test_inf_700a_5_i_finalize_teardown.py
- unit_tests/workflows/test_quick_fix_worktree_invariant.py

### 2026-10-14 13:00 — ac-fulfillment-gate (status: ok)
feedback-id: fb_2026-10-14_2961e011

All 3 ACs verified (BO-4300f-2, BO-4300f-2-ia, BO-4300f-2-ib). Resolver ok=true after 7 auto-fixes: implemented_by appended with files_touched ∩ diff for all three; covered_by for -ia and -ib set to their `# covers:` test files; work_status set to done via mark_ac_done.py (-ia, -ib, then composite BO-4300f-2 marked done). check_ac_schema.py exit 0 on all three. Commit phase may proceed.
Note: mark_ac_done's check-done-proof emitted REPORT-ONLY reachability findings for test_bo_4300f_2 (non-blocking).

### 2026-10-14 13:10 — documentation-verifier (status: ok)
feedback-id: fb_2026-10-14_beb8d5f6
completion_manifest:
  required_docs_list_parsed: true
  all_required_docs_present_in_diff: true
  no_placeholder_content_in_changed_docs: true
Documentation coverage verified: both required docs (docs/how-to/drive-epic-manually.md, docs/how-to/verify-precommit-active.md) are present in the working-tree diff (the branch range against origin/scaffold/EPIC-BO-4300 was empty for them) with real content; helper scan, TBD, token and stub checks all clean.

### 2026-10-14 14:00 — commit (status: ok)
feedback-id: fb_2026-10-14_127981b3

Committed f837478fb (part 2 of 2); part 1 = edc6d4a65. The file-size cuts on scripts/build.py, finalize-feature.js and plan-feature.js were genuine: the helper moved to scripts/build_target_guard.py and stale history and comments were removed. All pre-commit hooks passed with no bypass.

Q6 operational deletion of leafcutter-ai/.leafcutter/ is DEFERRED by user-approved decision dec-02bc263515e9d362 (2026-10-14): on main the main checkout's hooks, new-worktree provisioning and the paused-run store still depend on it. After the epic merges and is built: confirm no session has work in the main checkout, back up paused_runs/ and debugging/ outside the repo, ask the user per paused run, then delete it and the root .pre-commit-config.yaml with before/after listings recorded here. Before listing 2026-10-13: .agents agents commands config debugging gemini hooks paused_runs pre-commit-config.yaml scripts settings.json skills workflows. Never touch the parent install.
