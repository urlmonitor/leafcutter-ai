---
title: "Work identities: safe slugs, canonical spelling first, one identity per line"
ac_traceability:
  ac_path: docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
  l2:
  - BO-4300a-2
  l3: []
status: done
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
ac_coverage: 4/4
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
  - unit_tests/build_orchestration/_bo_4300a_2_probe.py
# out_of_scope: changed by tickets 01, 03, 04 and 09, merged into the epic commit (374cf7e06)
# this lane starts from; the scope guard diffs the whole branch against main. Not edited here.
out_of_scope:
  - scripts/suite_performance/_shared_layout_producer.py
  - scripts/suite_performance/_shared_layout_seed.py
  - templates/scripts/commit_guardian/ensure_precommit_config.py
  - templates/scripts/workspace_root.py
  - templates/scripts/worktree_canaries.py
  - templates/scripts/worktree_ensure_state.py
  - templates/scripts/worktree_git.py
  - templates/scripts/worktree_log_root.py
  - templates/scripts/worktree_remove.py
  - unit_tests/build_orchestration/_bo_4300f_2_fixtures.py
  - unit_tests/build_orchestration/_workspace_maker_builders.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/test_bo_4300a_1_budgets.py
  - unit_tests/build_orchestration/test_bo_4300a_1_marker_survival.py
  - unit_tests/build_orchestration/test_bo_4300c_2_never_prompts.py
  - unit_tests/build_orchestration/test_bo_4300e_2.py
  - unit_tests/build_orchestration/test_bo_4300e_2_i.py
  - unit_tests/build_orchestration/test_bo_4300e_2_iii.py
  - unit_tests/build_orchestration/test_bo_4300e_3.py
  - unit_tests/build_orchestration/test_bo_4300e_3_ii.py
  - unit_tests/build_orchestration/test_bo_4300f_4.py
  - unit_tests/commit_guardian/test_bo_1700c_1_iii_ordering_guard.py
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  ac-validator: signed_off
  ac-fulfillment-gate: signed_off
  commit: signed_off
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
- [x] AC-1: BO-4300a-2 IT0 (A5). `ensure --slug ..`, `--slug ...` and `--slug ''` each answer status error,
  code USAGE, exit 64, naming the identity. No folder, branch or lock appears in the landing place.
- [x] AC-2: BO-4300a-2 IT0 (A5). `slugify` maps `a..b` to `a.b`, `.hidden` to `hidden`, `x.lock` to `x`,
  and `v1.2` to `v1.2`. Every non-empty result passes `git check-ref-format --branch <kind>/<slug>` and is
  one path segment.
- [x] AC-3: BO-4300a-2 IT1 (A4). `Identity("ticket", "x").matches_branch("feature/x")` is false,
  `Identity("feature", "x").matches_branch("feature/x")` is true, and no declared alias in `LEGACY_ALIASES`
  equals any kind's canonical `<kind>/` prefix.
- [x] AC-4: BO-4300e-2 IT1 (M17). `discard_new_clone` deletes through the shared helper, and
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
- name: test_underscore_maps_to_hyphen_and_alone_is_empty
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    slugify maps a_b to a-b and a lone _ to the empty string.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_non_ascii_letters_are_dropped_current_behaviour
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    slugify of cafe-with-accent gives caf (pinned current behaviour).
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_windows_reserved_device_names_are_usage_and_write_nothing
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    ensure with --slug con, NUL, aux, com1, lpt9, con.txt answers error/USAGE exit 64 on every OS and writes nothing.
  framework: unittest
  type: behavioral
  angle: failure
- name: test_reserved_name_lookalikes_are_still_accepted
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    Control row: console, com10 and nul-x stay valid slugs.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_overlong_slug_is_usage_naming_the_limit_and_not_truncated
  file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
  covers:
  - BO-4300a-2
  asserts: >-
    A 65-character slug is USAGE naming 64, nothing written; 64 characters after normalisation pass untruncated.
  framework: unittest
  type: behavioral
  angle: boundary
- name: test_discard_new_clone_uses_the_shared_delete_helper (strengthened)
  file: unit_tests/build_orchestration/test_bo_4300a_2.py
  covers:
  - BO-4300a-2
  asserts: >-
    M17 AST check also catches 'from shutil import rmtree' (with alias) and bare rmtree calls, and requires discard_new_clone to use delete_whole_folder's return value.
  framework: unittest
  type: behavioral
  angle: discrimination
```

## Sign-offs
- [x] test-writer — 2026-10-22 16:00
- [x] python-coder — 2026-10-22 17:00
- [x] pr-reviewer — 2026-10-22 18:00
- [x] ac-validator — 2026-10-22 20:00
- [x] ac-fulfillment-gate — 2026-10-22 21:00
- [x] commit — 2026-10-22 22:00

## Comments

_(Append-only log -- leave blank when authoring.)_

### 2026-10-22 16:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Tests written (Linux image, each file alone: exit 1). Also repaired test drift from A4 in test_bo_4300a_2.py (classification: test_drift): dropped the ("ticket","feature/xray") alias row and changed the reachability test slug from "feature/Demo-Reach" to "Demo-Reach"; both relied on the alias A4 removes. Added helper unit_tests/build_orchestration/_bo_4300a_2_probe.py (fresh-interpreter probe of the deployed worktree_identity).
red_baseline:
  - test_name: test_dot_only_or_empty_identity_is_usage_and_writes_nothing
    file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
    kind: assertion
    error: "AssertionError: ('refused','FETCH_FAILED',2) != ('error','USAGE',64) for '..'; GIT_FAILED for '...'; ('ok','OK',0) with slug 'workspace' for ''"
  - test_name: test_slug_rules_give_one_valid_ref_segment
    file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
    kind: assertion
    error: "AssertionError: Lists differ: ['a..b', '.hidden', 'x.lock', 'v1.2', 'a', ...] != ['a.b', 'hidden', 'x', 'v1.2', 'a', ...]"
  - test_name: test_unsalvageable_input_has_no_default_slug
    file: unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py
    kind: assertion
    error: "AssertionError: Lists differ: ['..', 'workspace', '.lock'] != ['', '', '']"
  - test_name: test_feature_prefix_is_never_a_ticket_alias
    file: unit_tests/build_orchestration/test_bo_4300a_2.py
    kind: assertion
    error: "AssertionError: True is not False : {'ticket': True, 'feature': True, 'overlap': [['ticket', 'feature/']]}"
  - test_name: test_discard_new_clone_uses_the_shared_delete_helper
    file: unit_tests/build_orchestration/test_bo_4300a_2.py
    kind: assertion
    error: "AssertionError: Lists differ: [205] != [] : worktree_identity.py still calls rmtree itself at lines [205]"
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "worktree_identity.resolve/slugify (deployed)"
    consuming_side: "worktree.py ensure verb via run_maker subprocess (USAGE mapping, landing place)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "deployed worktree.py ensure --kind feature --slug <raw> via run_maker (CLI via subprocess)"

### 2026-10-22 17:00 — python-coder (status: ok)
feedback-id: (submit-failed)
Changed templates/scripts/worktree_identity.py only: A5 slugify (single dots, edges and .lock stripped, "" when empty; resolve raises wa.UsageError, which worktree.main maps to USAGE before any clone), A4 alias dropped plus load-time overlap check, M17 discard_new_clone uses worktree_remove.delete_whole_folder (no import cycle: every worktree_* module imports cleanly first). Linux family run green.
red_baseline_results:
  - test_dot_only_or_empty_identity_is_usage_and_writes_nothing: green
  - test_slug_rules_give_one_valid_ref_segment: green
  - test_unsalvageable_input_has_no_default_slug: green
  - test_feature_prefix_is_never_a_ticket_alias: green
  - test_discard_new_clone_uses_the_shared_delete_helper: green

### 2026-10-22 18:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
High: none blocking on the AC text. Medium: [M-1] slugify passes Windows reserved device names (con, nul, aux, com1, lpt1, con.txt) and has no length cap (300 chars stays 300), so ensure can still produce an unusable Windows folder; A5 does not list them, so raise as a follow-up. [M-2] unit_tests/build_orchestration/test_bo_4300a_2.py (A4 drift repair plus the M17 AST test) is modified but NOT staged; stage it before commit. [M-3] cmd_locate with --slug '..' now normalises to '' and looks at <place>/<kind>, answering NOT_FOUND, not USAGE (resolve() only guards ensure); remove has no --slug; verify accepts --slug but ignores it. [M-4] worktree_migrate.identity_for builds Identity(kind, slugify(...)) with no empty check (e.g. legacy 'feature/..'). Alias dropped, _check_alias_table runs at load, no import cycle (all worktree_* modules import cleanly). Tests could not run on Windows (fcntl layout lock).

### 2026-10-22 17:30 — python-coder (status: ok)
feedback-id: (submit-failed)
Rework for pr-reviewer: `_` now maps to `-`; new pure `slug_problem(slug) -> str | None` (empty, over 64 characters never truncated, Windows reserved device name before the first `.`) is called by `resolve`, which raises `wa.UsageError` naming the identity and reason; slugify docstring states non-ASCII letters are dropped. Linux family run green; ruff clean.

### 2026-10-22 19:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Follow-up to pr-reviewer M-1 (items 1-4) plus strengthened M17 AST check (item 5). New tests in test_bo_4300a_2_safe_slugs.py: underscore, non-ASCII pin, reserved device names via CLI, lookalike control row, 64-char limit via CLI plus resolve boundary. Test file test_bo_4300a_2.py: M17 test now catches rmtree via attribute, bare name and `from shutil import rmtree [as x]`, and requires delete_whole_folder's result to be consumed; docstring matches what it checks.
Red record: the coder's contract changes were already staged in templates/scripts/worktree_identity.py by the time I could run, so I did not observe a red run (label: reasoned). Against the tree the pr-reviewer saw, items 1-3 fail as assertion reds: `a_b` stays `a_b`, `con` and 65-char slugs are accepted (ok/0 instead of error/USAGE/64). Items 4 (non-ASCII) and the lookalike control pass by design. Green run (Docker, Linux): the whole -k bo_4300a_2 selection 19 passed; each file alone also passes (11 and 8). ast.parse and ruff clean; test files staged.
Wrong versions the tests catch: rmtree imported by name; delete_whole_folder called as a bare statement; truncating instead of refusing at 64; matching reserved names case-sensitively or only without extension; stripping `_` instead of mapping it to `-`.
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "worktree_identity.resolve/slugify (deployed)"
    consuming_side: "worktree.py ensure verb via run_maker subprocess (USAGE mapping, exit 64)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "deployed worktree.py ensure --kind feature --slug <raw> via run_maker (CLI via subprocess)"

### 2026-10-22 20:00 — ac-validator (status: ok)
feedback-id: (submit-failed)
completion_manifest:
  all_acs_covered: true
  store_alignment_clean: true
All 4 ACs covered (BO-4300a-2 as amended A4 and A5; store-alignment script exit 0; no delivers_to/expects_from on these ACs). Test evidence from the coder: Docker Linux, -k bo_4300a_2 gives 19 passed, each file alone passes; full family run still in progress (not verified by me).
AC-1 covered:
  implementation: templates/scripts/worktree_identity.py resolve() raises wa.UsageError when slug_problem(slug) is not None (empty slug has no default)
  test: test_dot_only_or_empty_identity_is_usage_and_writes_nothing (unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py)
AC-2 covered:
  implementation: templates/scripts/worktree_identity.py slugify(), _SLUG_DOTS, _SLUG_EDGE, .lock strip loop
  test: test_slug_rules_give_one_valid_ref_segment, test_unsalvageable_input_has_no_default_slug (test_bo_4300a_2_safe_slugs.py)
AC-3 covered:
  implementation: templates/scripts/worktree_identity.py LEGACY_ALIASES["ticket"] entry removed; _check_alias_table() runs at module load
  test: test_feature_prefix_is_never_a_ticket_alias (unit_tests/build_orchestration/test_bo_4300a_2.py)
AC-4 covered:
  implementation: templates/scripts/worktree_identity.py discard_new_clone calls wrm.delete_whole_folder; shutil/os/stat imports removed
  test: test_discard_new_clone_uses_the_shared_delete_helper (test_bo_4300a_2.py)
Beyond A5's literal text (noted, accepted): slug_problem() also refuses Windows reserved device names (con, prn, aux, nul, com1-9, lpt1-9, matched on the part before the first dot) and slugs over SLUG_MAX_LENGTH = 64 as USAGE, never truncating. Both serve A5's stated purpose (exactly one usable folder below <landing-root>/<kind>/). Tests: test_windows_reserved_device_names_are_usage_and_write_nothing, test_reserved_name_lookalikes_are_still_accepted, test_overlong_slug_is_usage_naming_the_limit_and_not_truncated. Also `_` now maps to `-` (A5 allows only letters, digits, '-' and single '.'). The BO-4300a-2.yaml it_requirements do not list the device-name or 64-limit rules; the AC text could be amended to record them.
Open, owned elsewhere: pr-reviewer M-3 (cmd_locate with '..' answers NOT_FOUND not USAGE; ticket 07) and M-4 (worktree_migrate.identity_for has no empty check; ticket 08).

### 2026-10-22 21:00 — ac-fulfillment-gate (status: ok)
feedback-id: (submit-failed)
Resolver: 1 AC resolved (BO-4300a-2, via traceability_block). Its only failing field is work_status (in_progress), which is intentionally left unchanged: ticket 07 (locate refusing an empty slug as USAGE) and ticket 08 (canonical-first cut-over identity) still build parts of this AC, so it must not be marked done by this ticket.
Auto-fixes applied (append-only, 2): in docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300a-2.yaml
- implemented_by += templates/scripts/worktree_identity.py (in files_touched and in the staged diff)
- covered_by += unit_tests/build_orchestration/test_bo_4300a_2_safe_slugs.py, unit_tests/build_orchestration/_bo_4300a_2_probe.py (the probe is a helper with no `# covers:` tag; added on the caller's instruction)
check_ac_schema.py exit 0. AC file staged with git add. No commit made.
Note: _bo_4300a_2_probe.py is not listed in the ticket's files_touched, though it is in the staged diff.

### 2026-10-22 22:00 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "fix(worktree): safe slugs, canonical spelling first, one identity per line"; staged files: the 6 files of this ticket.
