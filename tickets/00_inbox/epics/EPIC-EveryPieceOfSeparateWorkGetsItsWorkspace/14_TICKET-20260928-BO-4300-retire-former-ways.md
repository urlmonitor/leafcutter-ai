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
ac_coverage: 0/3
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
  ac-fulfillment-gate: needed
  ac-validator: needed
  adr-author: needed
  architect-review: needed
  commit: needed
  documentation-expert: needed
  documentation-verifier: needed
  frontend-coder: not_needed
  llm-expert: needed
  pr-reviewer: needed
  pull-request: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
  user-surface-smoker: not_needed
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

- [ ] AC-1: BO-4300f-2-ia -- Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces
- [ ] AC-2: BO-4300f-2-ib -- How-to guides carry no second recipe for workspaces
- [ ] AC-3: BO-4300f-2 -- The former ways of making a workspace are gone from what an install delivers

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

- [ ] AC-3: BO-4300f-2 -- The former ways of making a workspace are gone from what an install delivers

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### llm-expert

- [ ] AC-1: BO-4300f-2-ia -- Agent charters, skills, workflow texts and the rules file carry no second recipe for workspaces

**Depends on:** test-writer's red baseline for the tests above and the producers under Expects From.

### test-writer

- [ ] AC-1: red tests for BO-4300f-2-ia per `## Test Requirements`
- [ ] AC-2: red tests for BO-4300f-2-ib per `## Test Requirements`
- [ ] AC-3: red tests for BO-4300f-2 per `## Test Requirements`

**Delivers to:** python-coder, llm-expert (red baseline).

### documentation-expert

- [ ] AC-2: how-to | docs/how-to/drive-epic-manually.md | points at the maker and get-a-workspace.md
- [ ] AC-2: how-to | docs/how-to/verify-precommit-active.md | stale claims removed; points at the maker

### Expects From

- **BO-4300f-2-ia <- BO-4300a-3** (13_TICKET-20260928-BO-4300-docs-and-diagrams.md): docs/how-to/get-a-workspace.md exists as the single replacement page.
- **BO-4300f-2-ib <- BO-4300a-3** (13_TICKET-20260928-BO-4300-docs-and-diagrams.md): docs/how-to/get-a-workspace.md exists as the single replacement page.
- **BO-4300f-2 <- BO-4300f-1** (11_TICKET-20260928-BO-4300-workflow-routes.md): Every caller migrated to the maker before the former ways are removed.

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
- Touches data? No production data; developer repositories are protected by the ticket 02 session guard.
- Reversibility: all changes are code/docs on the epic branch; nothing ships until the epic PR merges.

## Sign-offs

- [ ] architect-review
- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] llm-expert
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] documentation-verifier
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
