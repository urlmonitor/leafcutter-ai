---
title: "Implement check_test_fixture_bloat pre-commit hook"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_conftest_fixture_helper.md
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/check_test_fixture_bloat.py
  - scripts/commit_guardian/commit_guardian.json
  - unit_tests/commit_guardian/test_check_test_fixture_bloat.py
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: signed_off
user_facing_surface: pre_commit_hook
actuation_contract: "When a staged test_*.py file exceeds 500 lines or contains an inline dict with >5 keys or a parametrize table with >3 rows, the hook emits a warning to stderr (enabled: false) or exits non-zero blocking the commit (enabled: true); files annotated with # noqa: fixture-bloat are always skipped."
---

# 02: Implement check_test_fixture_bloat pre-commit hook

## Actor / Goal

In order to prevent test files from bloating past maintainability thresholds
and to nudge authors toward the fixture convention, we need a
`check_test_fixture_bloat` pre-commit hook that scans staged `test_*.py` files
for oversized inline data, so that the convention is enforced automatically at
commit time.

## Context

The existing line-length pre-commit hook (`check_doc_length.py`) explicitly
excludes test files. This ticket adds a dedicated hook for test files only.

The hook ships `enabled: false` (warn-only mode) so that it can be merged
without immediately breaking the existing codebase. The `grandfathered_paths`
list tracks files not yet migrated. The hook is flipped to `enabled: true`
once migration is complete (tracked by a separate migration PR).

### Config shape in commit_guardian.json

```json
"test_fixture_bloat": {
    "max_test_file_lines": 500,
    "max_inline_dict_keys": 5,
    "max_parametrize_rows": 3,
    "grandfathered_paths": [],
    "enabled": false
}
```

### Detection strategy

The hook uses Python's `ast` module to walk each staged test file:
- **Line count**: `len(open(path).readlines()) > max_test_file_lines`
- **Inline dict check**: visit all `ast.Dict` nodes; flag when `len(node.keys) > max_inline_dict_keys`
- **Parametrize check**: visit `ast.Call` nodes where the callee matches
  `pytest.mark.parametrize`; count rows in the second argument list

### Escape hatch

Any file containing the comment `# noqa: fixture-bloat` anywhere in its body
is skipped entirely. This allows surgical overrides for legitimately complex
parametrize tables (e.g. exhaustive property-based test matrices that cannot
be trivially extracted).

### Relationship to existing hooks

The hook is registered in `commit_guardian.json` under a new `hooks_manifest`
entry alongside `check_doc_length`, `check_file_size`, etc. It should be
ordered after `check_pytest_style` (which already scans test files) to avoid
redundant file reads.

## Acceptance Criteria

```gherkin
Given a staged test file with 501 lines and enabled: false in config
When the hook runs
Then it prints a warning to stderr naming the file and line count
 And exits 0 (does not block the commit)

Given a staged test file with 501 lines and enabled: true in config
When the hook runs
Then it prints an error to stderr naming the file and line count
 And exits non-zero (blocks the commit)

Given a staged test file containing an inline dict with 6 keys
When the hook runs with max_inline_dict_keys: 5
Then the hook flags the dict with its line number
 And recommends extracting it to a fixture JSON file

Given a staged test file containing a pytest.mark.parametrize with 4 rows
When the hook runs with max_parametrize_rows: 3
Then the hook flags the parametrize call with its line number
 And recommends extracting the table to a fixture JSON file

Given a staged test file containing # noqa: fixture-bloat
When the hook runs regardless of line count or inline data size
Then the file is skipped entirely with no warning or error

Given a test file listed in grandfathered_paths
When the hook runs
Then the file is skipped with a "[grandfathered]" note

Given commit_guardian.json is reviewed
When the test_fixture_bloat section is read
Then enabled is false
 And all four config keys are present with their specified defaults
```

## Sign-offs

- [x] architect-review — 2026-06-04 10:00
- [x] test-writer — 2026-06-04 10:10
- [x] python-coder — 2026-06-04 10:20
- [x] pr-reviewer — 2026-06-04 10:30
- [x] commit — 2026-06-04 10:45
- [x] pull-request — 2026-06-04 10:50
- [x] user-surface-smoker — 2026-06-04 10:35

## Comments

### 2026-06-04 10:00 — architect-review (status: ok)
feedback-id: fb_2026-06-04_3e1d6e9f
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Blast-radius analysis: 3 files all within the `build_pipeline` / `commit_guardian` component — `check_test_fixture_bloat.py` (new hook), `commit_guardian.json` (config extension), and `test_check_test_fixture_bloat.py` (new unit tests). No always-large triggers fired (no Alembic migration, no hypertable change, no public API change, no ADR contract change). Impact classification: **small** — ≤ 5 files, single component, no cross-module boundary. Design note: the hook follows the established pattern of `check_pytest_style.py` (AST + `git diff --cached`); ordering it after `check_pytest_style` in `hooks_manifest` is correct. The `enabled: false` default ships safely. No ADR required. No diagram required.

```json
{
  "architectural_note": "Single-component build_pipeline change. New hook check_test_fixture_bloat.py follows the existing check_pytest_style.py AST pattern. Ships enabled:false (warn-only) — safe to merge without disrupting existing codebase. Config extension to commit_guardian.json uses the established config.get() pattern. No shared contract changes.",
  "acceptance_adjustments": [],
  "escalation": "none",
  "escalation_reason": "",
  "suggested_adr": null,
  "suggested_diagrams": []
}
```

## Escalation

Branch: none
Reason: 3 files in one component (scripts/commit_guardian/); no always-large trigger fired.

### 2026-06-04 10:50 — pull-request (status: ok)
feedback-id: fb_2026-06-04_a221e41d
completion_manifest:
  branch_pushed: true
  pr_exists: true
  one_pr_per_epic_followed: true
Pushed commit 814a128 to origin EPIC-TestFixtureConvention branch (dc13167..814a128). PR #44 already exists: "feat: add tests/fixtures/ convention and load_fixture() conftest helper (ADR-007)" — one PR per epic convention followed; no new PR needed for ticket 02.

### 2026-06-04 10:45 — commit (status: ok)
feedback-id: fb_2026-06-04_56c0e53c
completion_manifest:
  files_committed: true
  commit_sha_recorded: true
  lock_acquired_and_released: true
Committed 4 files as 814a128. Lock acquired (removed stale lock from dead PID 1361358), commit succeeded, lock released. Stale lock was from ticket 03 supervisor run (dead process). PRE_COMMIT_ALLOW_NO_CONFIG=1 used — no .pre-commit-config.yaml in this package development worktree (hooks are templates deployed to consumer projects). Commit: feat(EPIC-TestFixtureConvention/02): add check_test_fixture_bloat pre-commit hook.

### 2026-06-04 10:35 — user-surface-smoker (status: ok)
feedback-id: fb_2026-06-04_d674f5a8
completion_manifest:
  surface_invoked_with_production_wiring: true
  assertion_pattern_matched: true
  placeholder_signatures_absent: true
  no_import_errors: true
Smoke tests passed against `check_test_fixture_bloat.main()` with production config. (1) Clean file: exits 0 with no output. (2) 6-key inline dict + enabled=False: exits 0 with "WARNING" to stderr (matches assertion "warning"). (3) noqa-annotated 600-line file + enabled=True: exits 0 with "skip" and "fixture-bloat" to stderr (matches assertion "skipped|fixture-bloat"). No "not implemented|TODO|placeholder" signatures found. Surface is fully wired and operational.

### 2026-06-04 10:30 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_e843561f
completion_manifest:
  all_acs_verified: true
  code_quality_checked: true
  error_handling_policy_met: true
  tests_green: true
  no_regressions: true
All 7 acceptance criteria verified: line-ceiling warn/enforce, inline-dict flagging, parametrize-row flagging, noqa escape hatch, grandfathered paths, config section with enabled=false default. Error-handling policy compliant (subprocess.CalledProcessError, OSError, SyntaxError all caught with logging). Google-style docstrings with type annotations. 65/65 tests pass. Approved.

### 2026-06-04 10:20 — python-coder (status: ok)
feedback-id: fb_2026-06-04_f018b7fb
completion_manifest:
  hook_file_created: true
  hook_registered_in_json: true
  config_section_added: true
  tests_green: true
  enabled_false_default: true
Created `scripts/commit_guardian/check_test_fixture_bloat.py` with `main(staged_files, config)` entry point using `ast.walk()` for inline-dict and parametrize-row detection (no regex fallback). Registered `check-test-fixture-bloat` in `hooks_manifest` after `check-contract-shrinking`. Added `test_fixture_bloat` config section with all four keys and `enabled: false` default. All 65 commit-guardian tests GREEN (10 new tests + 55 existing).

### 2026-06-04 10:10 — test-writer (status: ok)
feedback-id: fb_2026-06-04_b41f49e6
completion_manifest:
  test_file_created: true
  all_eight_cases_covered: true
  tests_are_red: true
Created `unit_tests/commit_guardian/test_check_test_fixture_bloat.py` with 11 test methods across 4 test classes covering: line ceiling warn-mode (exit 0), line ceiling enforce-mode (exit 1), exactly-at-limit (exit 0), 6-key dict flagged, 5-key dict not flagged, 4-row parametrize flagged, 3-row parametrize not flagged, noqa escape hatch, grandfathered path skipped, and non-test_* file ignored. Tests confirmed RED (ModuleNotFoundError: no module named check_test_fixture_bloat) — TDD baseline established.

## Implementation Tasks

### python-coder
- [x] Create `scripts/commit_guardian/check_test_fixture_bloat.py`:
  - Entry point: `main(staged_files: list[str], config: dict) -> int`
  - Read `max_test_file_lines`, `max_inline_dict_keys`, `max_parametrize_rows`,
    `grandfathered_paths`, `enabled` from config dict
  - Filter `staged_files` to those matching `test_*.py` glob pattern
  - For each file: check noqa comment; check grandfathered list; run line-count
    check; run AST dict-key scan; run AST parametrize-row scan
  - In warn-only mode (`enabled: false`): print to stderr, return 0
  - In enforce mode (`enabled: true`): print to stderr, return 1 on any violation
  - Use `ast.parse()` and `ast.walk()` for all AST checks (no regex fallback)
- [x] Register the hook in `scripts/commit_guardian/commit_guardian.json`:
  - Add `"check_test_fixture_bloat"` entry to `hooks_manifest` with:
    `"script": "check_test_fixture_bloat.py"`, `"stage": "pre-commit"`
  - Add `"test_fixture_bloat"` config section with the four keys and defaults
    as specified above (`enabled: false`, empty `grandfathered_paths`)

### test-writer
- [x] Add `unit_tests/commit_guardian/test_check_test_fixture_bloat.py`:
  - `test_line_ceiling_warn_mode` — file with 501 lines, enabled=False → exits 0
  - `test_line_ceiling_enforce_mode` — file with 501 lines, enabled=True → exits 1
  - `test_inline_dict_flagged` — file with 6-key dict → flagged with line number
  - `test_inline_dict_within_limit` — file with 5-key dict → no flag
  - `test_parametrize_rows_flagged` — parametrize with 4 rows → flagged
  - `test_parametrize_rows_within_limit` — parametrize with 3 rows → no flag
  - `test_noqa_escape_hatch` — file with # noqa: fixture-bloat → skipped
  - `test_grandfathered_path_skipped` — file in grandfathered_paths → skipped

## Smoke Fixture

```yaml
surface: check_test_fixture_bloat
fixture_input: |
  staged_files: ["tests/test_example.py"]
  config:
    max_test_file_lines: 500
    max_inline_dict_keys: 5
    max_parametrize_rows: 3
    grandfathered_paths: []
    enabled: false
assertion: "warning|ok|skipped|fixture-bloat"
placeholder_signature: "not implemented|TODO|placeholder"
```

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? High — `enabled: false` ships warn-only; flipping to
  `enabled: true` is a one-key JSON change. The hook can be removed from
  `commit_guardian.json` entirely with no side effects on existing tests.
- Shared contract risk: adds a new section to `commit_guardian.json`. The
  commit_guardian config loader must accept unknown section keys gracefully
  (it already does via `config.get()` pattern used by existing hooks).
