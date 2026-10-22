---
title: "Workflows run the maker by its absolute path and stop when a shell step fails"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2: []
  l3:
  - BO-4300a-1-ia
  - BO-4300a-1-ib
status: todo
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: internal
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M13
  - M16
  - M5
files_touched:
  - templates/workflows-js/_shared/workspace-answer.js
  - templates/workflows-js/plan-feature.js
  - templates/workflows-js/build-epic.js
  - templates/workflows-js/build-feature.js
  - templates/workflows-js/build-ticket.js
  - templates/workflows-js/fast-lane-ship.js
  - templates/workflows-js/finalize-feature.js
  - templates/workflows-js/quick-fix.js
  - templates/agents/worktree-agent.md
  - templates/skills/build-feature-ops-notes/SKILL.md
  - templates/skills/ship/SKILL.md
  - unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  - unit_tests/build_orchestration/_bo_4300a_1_ia_fixtures.py
  - unit_tests/build_orchestration/test_bo_4300a_1_ib.py
agents:
  test-writer: needed
  llm-expert: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
---

# 02: Workflows run the maker by its absolute path and stop when a shell step fails

## Actor / Goal
A workflow asks for a workspace with one exact absolute command, so the request works whatever folder the
shell-runner happens to be in. A shell step that gets no real result ends the run. The step is never taken
as having run.

## Context
- **Defect M13 (MEDIUM).** Workflows build the maker command as
  `python3 {{config.output_root}}/scripts/worktree.py ...`. `{{config.output_root}}` renders to the relative
  `.leafcutter`, so the command is cwd-relative.
  - **ACs and decisions violated:** the BO-4300a-1-ia it_requirement "run one exact absolute command
    unchanged", ADR-070 §1.2 and §2.1, and the entry skills' own "never a cwd-relative path" rule
    (BO-4300a-1-ib).
  - **Sites, verified against the current tree:**
    - `build-epic.js:292`
    - `build-feature.js:1522` (the `workspaceConfirmHandedIn` call) and `:1597`
    - `build-ticket.js:1373`
    - `fast-lane-ship.js:773`
    - `finalize-feature.js:448`, `:503` (remove) and `:519`
    - `quick-fix.js:245`
  - **Docs that tell an agent to run `python scripts/worktree.py`:**
    - `templates/agents/worktree-agent.md:85`
    - `templates/skills/build-feature-ops-notes/SKILL.md:209` and `:280`
    - `templates/skills/ship/SKILL.md:18` (locate) and `:52` (remove)
  - **Quoting:** interpolated slugs are unquoted, e.g. `--slug ${epicSlug}` (build-epic.js:292),
    `--slug ${buildSlug}` and `--slug " + finalizeSlug`. Main's KI-BO-20261021 (1f4944742) covers this
    class of bug.
- **Absolute-path resolver:** `resolveRepoAnchoredMakerPath` lives only in `plan-feature.js:2097`. It
  hard-codes `/.leafcutter/scripts/worktree.py`; reconcile that with `{{config.output_root}}` when the
  resolver moves.
- **Defect M16 (LOW).** At `plan-feature.js:2146`, `shellStepDispatch("git branch --show-current", ...)`
  names no location.
  - Its transport failure is caught as best effort (`currentBranchDispatchFailed`, `:2144-2154`).
  - This violates ADR-070 §1.2 ("the command MUST say where it acts") and §5.2 ("no reply ... MUST end the
    run").
  - The same unanchored spelling is the fallback at `:291` and `:1203`.
  - **AC:** BO-4300a-1-ia criteria and IT4 (a declined, prose or empty shell-step answer ends the workflow
    with an error quoting the answer).
- **M5 caller re-check.** Ticket 07 makes `verify` refuse with `VERIFY_FAILED` and moves `kind`, `slug` and
  `branch` to the top level (keeping `marker` as an extra field).
  - `workspaceConfirmHandedIn` / `workspaceVerifyCommand` (`_shared/workspace-answer.js:145-161`) must
    already stop on any non-ok verify answer.
  - `workspaceBranch` (the next function) must read a top-level `branch` first, then fall back to
    `marker.branch`, so that it works before and after ticket 07.
- Workflow tests for this family are Python `unittest` modules that drive the deployed workflows through the
  existing harness (`_bo_4300a_1_ia_fixtures.py`, `_bo_4300c_3_fixtures.py`). There is no JS test runner for
  `templates/workflows-js`.

## Scope
1. Move `resolveRepoAnchoredMakerPath` (and `MAKER_PROBES`) from `plan-feature.js` into
   `_shared/workspace-answer.js`. Every workflow builds each maker command (ensure, verify, remove) from its
   absolute result, quotes every interpolated path and slug, and halts with the resolver's reason when it
   fails.
2. `plan-feature.js`: run the current-branch check as `git -C "<absolute project>" branch --show-current`
   at all three sites. A transport failure ends the run with an error. It is no longer best effort.
3. Rewrite the five doc sites (llm-expert) to the exact absolute form, as BO-4300a-1-ib's entry skills do.
   The form is `python "<absolute install>/scripts/worktree.py" ...`, with the absolute path obtained from
   `worktree.py where` or the resolver. Never a cwd-relative `python scripts/...`.
4. Apply the M5 caller re-check in `_shared/workspace-answer.js` as described in Context.

## Acceptance Criteria
- [ ] AC-1: BO-4300a-1-ia ("one exact absolute command, unchanged"). In every deployed workflow, every
  dispatched maker command (ensure, verify, remove) starts with an absolute, quoted path to `worktree.py`
  and quotes every interpolated slug and path. The harness, run from a cwd that is not the project, records
  no maker command with a relative path.
- [ ] AC-2: BO-4300a-1-ia IT4 (ADR-070 §5.2). When the current-branch shell step of `plan-feature.js` gets
  no reply (a transport failure), the run ends with `status: error` and dispatches nothing after it. The
  command it sent is `git -C "<absolute project>" branch --show-current`.
- [ ] AC-3: BO-4300a-1-ib. No agent, skill or command template under `templates/` tells an agent to run
  `python scripts/worktree.py` or `python3 scripts/worktree.py` by a cwd-relative path; the lint finds zero
  hits.
- [ ] AC-4: BO-4300a-1-ia (M5 caller re-check). A handed-in location whose verify answer is
  `refused`/`VERIFY_FAILED` stops the run before any step, quoting the answer. `workspaceBranch` returns the
  top-level `branch` when present, and `marker.branch` otherwise.

## Test Requirements

```yaml
tests:
- name: test_every_workflow_dispatches_the_maker_by_an_absolute_quoted_path
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    For each deployed workspace-consuming workflow (consuming_workflows()), driven by the existing harness
    from a cwd outside the project, every recorded maker dispatch (ensure / verify / remove) starts with
    an absolute quoted path ending in scripts/worktree.py and quotes its --slug / --path values.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_branch_check_transport_failure_ends_the_run
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    The deployed plan-feature.js, with the detect-current-branch dispatch made to throw, ends with
    status error and no later dispatch. The command sent carries `git -C "<abs>"`.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_refused_verify_of_handed_in_location_stops_the_run
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia.py
  covers:
  - BO-4300a-1-ia
  asserts: >-
    build-feature.js with args.workspace handed in as a location, and the verify dispatch scripted to
    answer refused/VERIFY_FAILED, stops before any phase dispatch and quotes the answer.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_no_template_runs_the_maker_by_a_cwd_relative_path
  file: unit_tests/build_orchestration/test_bo_4300a_1_ia_lint.py
  covers:
  - BO-4300a-1-ib
  asserts: >-
    A scan of templates/agents, templates/skills, templates/commands and templates/workflows-js finds no
    `python(3)? scripts/worktree.py` and no `{{config.output_root}}/scripts/worktree.py` maker command.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [ ] test-writer
- [ ] llm-expert
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
