---
title: "The workspace maker builds every workspace pointing at the project's durable log root, and main's tests reach the maker"
ac_traceability:
  id: INF-500d-4-iii
  path: docs/acceptance-criteria/infrastructure/INF-500-operational-observability/INF-500d-4-iii.yaml
status: todo
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-16'
last_updated: '2026-10-16'
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
  - found-at-main-merge-83db3c9ba
files_touched:
  - templates/scripts/worktree_readiness.py
  - unit_tests/portability/test_inf_500d_4_iii.py
  - unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
  - unit_tests/workflows/_bo2400f5iii_fixtures.py
  - unit_tests/workflows/test_bo2400f5iii_declined_step_core.py
  - unit_tests/workflows/test_bo2400f5iii_false_positives_and_release.py
  - unit_tests/workflows/test_bo2400f5iii_strong_markers_and_signals.py
  - unit_tests/build_orchestration/_bo4400f1_routes.py
  - unit_tests/commit_guardian/test_bp_1300e_1_iv.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  frontend-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  documentation-verifier: not_needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  user-surface-smoker: not_needed
  commit: needed
  pull-request: not_needed
---

# 17: The workspace maker builds every workspace pointing at the project's durable log root, and main's tests reach the maker

## Actor / Goal
In order for logs written inside a maker-made workspace to survive its removal (INF-500d-4-iii), the maker's install build must receive the project's enduring log root, exactly as the retired bootstrap did. Main's tests that still drive the retired paths must reach the maker instead, so the epic can merge with a green suite.

## Context
- **Found:** 2026-10-16, merging origin/main into the epic (merge commit 83db3c9ba). Main's INF-500d-4-iii (commits 01bf0610a, 59ed536f8) put the log-root pass-through into `setup_ticket_worktree.py`'s `_bootstrap`. Ticket 14 (BO-4300f-2) deleted that script, so the behaviour exists nowhere on the epic branch. A maker-made workspace's build now declares its own `debugging/logs`, and those logs die with the workspace.
- **What the retired bootstrap did:**
  - It read `<main>/.leafcutter/config/knowledge_sink.json` and used `operational_log_root`, or `Path(knowledge_emission_sink).parent` for an older declaration. The root was never derived from the repository path.
  - When the file was absent, unreadable, keyless or held a relative root, it printed `WARNING: no enduring log root readable from <path> (<why>); logs written in this worktree will not survive its removal.` and passed `--no-log-root`. Otherwise it passed `--log-root <root>`.
  - It ran `build.py --target-dir <worktree> [flag]` with stderr captured. If the workspace's own `build.py` predated the flags (exit 2 with `unrecognized arguments`), it retried once without the flag and warned.
- **Where the maker builds:** `templates/scripts/worktree_readiness.py` → `run_install_build()` runs `[python, <ws>/scripts/build.py, --target-dir, ws, --config-path, cfg]` with `LEAFCUTTER_SHIM_STRATEGY=copy`. It passes neither flag and takes no project-install path, so the caller must supply it. Architect-review decides where the project's install is read from in each layout, including the package repository (which holds no install after Q6).
- **Tests main added that reach the retired paths:**
  - `unit_tests/portability/test_inf_500d_4_iii.py` and `test_inf_500d_4_iii_older_worktree_build.py` call the deleted script's `_bootstrap`.
  - BO-2400f-5-iii fixtures and tests (`unit_tests/workflows/_bo2400f5iii_fixtures.py`, `test_bo2400f5iii_*.py`) and `unit_tests/build_orchestration/_bo4400f1_routes.py` script the old fast-lane `worktree-agent` / `fastlane-worktree(-verify)` steps and the old `resolve-connected` reply shape.
  - `unit_tests/commit_guardian/test_bp_1300e_1_iv.py:29,31` spells `git worktree add` directly, a hit for the BO-4300f-2 census.
- The merge re-applied main's BO-2400f-5-iii decline classification on the maker-based resolve step in `fast-lane-ship.js`. Tests must prove that path, not the old shape.

## Acceptance Criteria
- [ ] AC-1: A workspace the deployed maker makes has a `config/knowledge_sink.json` whose `operational_log_root` is the project's enduring root. Its feedback, telemetry and knowledge sinks sit directly under that root (INF-500d-4-iii).
- [ ] AC-2: When the project's root cannot be read, the maker's answer stays ok. The build records the empty declaration (`--no-log-root`), and the warning names the path tried and why.
- [ ] AC-3: A workspace whose own `build.py` predates the flags is still built: one retry without the flag, plus a warning.
- [ ] AC-4: The INF-500d-4-iii proofs run the deployed maker as a separate process, not the deleted script. The BO-2400f-5-iii and BO-4400f-1 tests drive the maker-based fast-lane steps. `test_bp_1300e_1_iv.py` makes its linked checkout through the exempt `link_checkout` helper. The BO-4300f-2 census stays empty.

## Test Requirements

```yaml
tests:
- name: test_maker_workspace_inherits_the_projects_durable_log_root
  file: unit_tests/portability/test_inf_500d_4_iii.py
  covers:
  - INF-500d-4-iii
  asserts: The deployed maker's ok answer names a workspace whose knowledge_sink.json records the project's operational_log_root (absolute) and every sink directly under it.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_unreadable_project_root_builds_with_no_log_root_and_warns
  file: unit_tests/portability/test_inf_500d_4_iii.py
  covers:
  - INF-500d-4-iii
  asserts: With the project's knowledge_sink.json absent or relative, the maker still answers ok, the workspace records {} and the warning names the path and reason.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_older_workspace_build_is_retried_without_the_flag
  file: unit_tests/portability/test_inf_500d_4_iii_older_worktree_build.py
  covers:
  - INF-500d-4-iii
  asserts: A fixture build that rejects --log-root with exit 2 is retried once without it; the workspace is built and a warning is printed.
  framework: unittest
  type: behavioral
  angle: failure
```

## Implementation Notes
- Use the BO-4300f-4 fixture module (`_workspace_maker_fixtures.py`) for deployed-maker runs and real temporary hubs. Never mock git, and never spawn the package's own `build.py` (CLAUDE.md "Tests must not spawn their own build.py"). Fixture projects carry the stub build entry point.
- Do not re-create any former way: no `git worktree add/remove` outside the exemptions, and no own repository search.
- `worktree_readiness.py` is near its size limit. Keep any helper small, or put it in its own module.

## Agent Contracts

### python-coder
- [ ] AC-1, AC-2, AC-3 in `templates/scripts/worktree_readiness.py` (and the maker's call site).

### test-writer
- [ ] AC-4 test migrations and the three tests above (red first).

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

_(Append-only log — leave blank when authoring.)_
