---
title: "Implement check_test_fixture_bloat pre-commit hook"
status: todo
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
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] user-surface-smoker

## Comments

## Implementation Tasks

### python-coder
- [ ] Create `scripts/commit_guardian/check_test_fixture_bloat.py`:
  - Entry point: `main(staged_files: list[str], config: dict) -> int`
  - Read `max_test_file_lines`, `max_inline_dict_keys`, `max_parametrize_rows`,
    `grandfathered_paths`, `enabled` from config dict
  - Filter `staged_files` to those matching `test_*.py` glob pattern
  - For each file: check noqa comment; check grandfathered list; run line-count
    check; run AST dict-key scan; run AST parametrize-row scan
  - In warn-only mode (`enabled: false`): print to stderr, return 0
  - In enforce mode (`enabled: true`): print to stderr, return 1 on any violation
  - Use `ast.parse()` and `ast.walk()` for all AST checks (no regex fallback)
- [ ] Register the hook in `scripts/commit_guardian/commit_guardian.json`:
  - Add `"check_test_fixture_bloat"` entry to `hooks_manifest` with:
    `"script": "check_test_fixture_bloat.py"`, `"stage": "pre-commit"`
  - Add `"test_fixture_bloat"` config section with the four keys and defaults
    as specified above (`enabled: false`, empty `grandfathered_paths`)

### test-writer
- [ ] Add `unit_tests/commit_guardian/test_check_test_fixture_bloat.py`:
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
