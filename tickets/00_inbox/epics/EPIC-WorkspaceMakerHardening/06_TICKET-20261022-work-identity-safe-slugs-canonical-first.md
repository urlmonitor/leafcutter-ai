---
title: "Work identities: safe slugs, canonical spelling first, one identity per line"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-2
  l3: []
status: todo
components:
  - worktree_manager
  - build_orchestration
created: '2026-10-22'
last_updated: '2026-10-22'
depends_on:
  - 01_TICKET-20261022-maker-never-waits-for-input.md
  - 04_TICKET-20261022-clearing-stays-inside-project.md
priority: critical
roadmap_phase: phase_1
advances_current_outcome: true
change_target: code
risk_surface: safety
complexity: medium
requires_adr: false
requires_diagram: false
tags:
  - BO-4300
  - bo4300-hardening
  - M11
  - M10
  - M17
files_touched:
  - templates/scripts/worktree_identity.py
  - unit_tests/build_orchestration/test_bo_4300a_2.py
  - unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  ac-validator: needed
  ac-fulfillment-gate: needed
  commit: needed
---

# 06: Work identities: safe slugs, canonical spelling first, one identity per line

## Actor / Goal
Anyone names a piece of work. The name must always become a valid line-of-work name and exactly one folder
below `<landing-root>/<kind>/`. A spelling that is canonical for one kind must never be read as an alias of
another kind, so one line of work always has one identity and one workspace.

## Context
All references are verified against the current tree, in `templates/scripts/worktree_identity.py`.

- **M11 (MEDIUM; BO-4300a-2 IT0 as amended by A5; BO-4300b-2 / b-2-i).** `slugify` (line 53) keeps dots
  (`_SLUG_DISALLOWED = [^a-z0-9._-]+`, line 51).
  - `--slug ..` resolves to `<landing>/feature/..`, which is the landing root itself.
  - `a..b`, a trailing `.lock` or a leading `.` give invalid ref names that fail late, after the clone.
  - Empty input silently becomes `"workspace"`.
  - Fix (A5):
    - Collapse `\.{2,}` to `.`.
    - Strip leading and trailing `-` and `.`.
    - Strip a `.lock` suffix.
    - Allow single dots.
    - An empty result is USAGE (status error, exit 64) naming the identity. Nothing is written and no
      default slug is substituted.
  - `resolve` (line 92) raising `wa.UsageError` is enough: `worktree.main` already maps it to USAGE.
  - Port source: the regex tail of v1 `workspace_core.normalize_slug`.
- **M10 naming table (MEDIUM; BO-4300a-2 IT1 as amended by A4, option A).**
  - `LEGACY_ALIASES["ticket"]` (line 46) declares `feature/` as a ticket alias, although `feature/` is
    kind feature's canonical prefix.
  - `Identity.matches_branch` (line 86) therefore matches `feature/x` for `Identity("ticket", "x")`.
  - Fix: drop the entry. Add a check that no declared alias equals any kind's canonical `<kind>/` prefix,
    so the table can never again declare a spelling as an alias of one kind while it is canonical for
    another. `feature/<slug>` always resolves to kind feature.
  - The cut-over's own resolution order (`worktree_migrate.identity_for`, M10 in the cut-over) is
    ticket 08.
- **M17 (BO-4300e-2 IT1).** `discard_new_clone` (line 199) has its own inline `_force`/`shutil.rmtree`
  (lines 201-205), without the `\\?\` long-path prefix or `onexc`. Replace them with the shared
  whole-folder delete helper that ticket 04 exposes in `worktree_remove.py`.
  - This is safe for import order: `worktree_remove` imports neither `worktree_identity` nor anything that
    imports it at module level (`worktree_git` imports it only inside a function).
- Ticket 01 edits `_show_bytes` in this file in wave 1, and this ticket owns the rest in wave 2. The
  callers `worktree_git.normalize_slug` (`worktree_git.py:200`), `worktree_admin.cmd_locate` and
  `worktree_migrate.identity_for` are owned by tickets 05, 07 and 08 respectively; they pick up the new
  behaviour through `wi.resolve` / `wi.slugify`.

## Scope
1. A5 slug rules in `slugify`/`normalize_slug`, with an empty result raising `wa.UsageError` from
   `resolve`.
2. Drop `ticket <- feature/<slug>`, and add a module-load check against alias/canonical overlap.
3. `discard_new_clone` uses the shared delete helper.

## Acceptance Criteria
- [ ] AC-1: BO-4300a-2 IT0 (A5). `ensure --slug ..`, `--slug ...` and `--slug ''` each answer status error,
  code USAGE, exit 64, naming the identity. No folder, branch or lock appears in the landing place.
- [ ] AC-2: BO-4300a-2 IT0 (A5). `slugify` maps `a..b` to `a.b`, `.hidden` to `hidden`, `x.lock` to `x`,
  and `v1.2` to `v1.2`. Every non-empty result passes `git check-ref-format --branch <kind>/<slug>` and is
  one path segment.
- [ ] AC-3: BO-4300a-2 IT1 (A4). `Identity("ticket", "x").matches_branch("feature/x")` is false,
  `Identity("feature", "x").matches_branch("feature/x")` is true, and no declared alias in `LEGACY_ALIASES`
  equals any kind's canonical `<kind>/` prefix.
- [ ] AC-4: BO-4300e-2 IT1 (M17). `discard_new_clone` deletes through the shared helper, and
  `worktree_identity.py` contains no `shutil.rmtree` call of its own.

## Test Requirements

```yaml
tests:
- name: test_dot_only_or_empty_identity_is_usage_and_writes_nothing
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    make_project. For --slug '..', '...' and '' in turn, run_maker ensure --kind feature answers
    error/USAGE with exit 64, and the message names the identity. The landing place (fx['landing_place'])
    is absent or empty afterwards, and the hub and project have no new branch.
  framework: unittest
  type: behavioral
  angle: deployed
- name: test_slug_rules_give_one_valid_ref_segment
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    The deployed worktree_identity.slugify maps a..b, .hidden, x.lock, v1.2 and "-a-" to a.b, hidden, x,
    v1.2 and a. Each result contains no '/' and passes `git check-ref-format --branch feature/<slug>`.
  framework: unittest
  type: behavioral
- name: test_feature_prefix_is_never_a_ticket_alias
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: >-
    Identity('ticket','x').matches_branch('feature/x') is False and Identity('feature','x') matches it.
    For every kind, no alias prefix in LEGACY_ALIASES equals f'{k}/' for any kind k.
  framework: unittest
  type: behavioral
- name: test_discard_new_clone_uses_the_shared_delete_helper
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: >-
    An AST scan of the deployed worktree_identity.py finds no shutil.rmtree call. A failed checkout after a
    fresh clone (USAGE-free refusal path) leaves no folder in the landing place.
  framework: unittest
  type: behavioral
```

## Sign-offs
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] ac-validator
- [ ] ac-fulfillment-gate
- [ ] commit

## Comments

_(Append-only log -- leave blank when authoring.)_
