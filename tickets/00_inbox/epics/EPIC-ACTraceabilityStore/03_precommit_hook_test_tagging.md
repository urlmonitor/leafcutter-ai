---
title: "Pre-commit hook: every test function must have a # covers: XX-NNN tag"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/commit-guardian/check_test_ac_tags.py
  - templates/commit-guardian/commit_guardian.json
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Pre-commit hook: every test function must have a # covers: XX-NNN tag

## Actor / Goal

In order to maintain machine-readable traceability between tests and ACs, we
need a pre-commit hook that checks every Python test function in staged files
for a `# covers: XX-NNN` comment, so that uncovered tests are caught at commit
time before they accumulate into an untracked backlog.

## Context

The `# covers:` tag is the only machine-readable link from a test to an AC.
Without enforcement, test authors will forget to add it and the coverage
mapping will degrade quickly.

The hook checks only test files (files matching `**/test_*.py` or
`**/*_test.py`). For each test function in a staged test file, it looks for
a `# covers: XX-NNN` comment on the function's first line, the line above
the `def`, or in the function's docstring.

### Grace period

Per the ADR from ticket 01, the hook launches in **warning mode** (exit 0
with a warning message). A follow-up grace-period ticket (not in this epic)
will flip it to **error mode** (exit 1) after existing tests have been
backfilled with `covers:` tags.

The mode is controlled by a field in `commit_guardian.json`:
`"test_ac_tag_enforcement": "warn"` (default) or `"error"`.

### Tag format

```python
def test_merge_main_executes_before_tests():
    # covers: FIN-001
    ...
```

Or in a docstring:

```python
def test_merge_main_executes_before_tests():
    """covers: FIN-001 — verifies merge-main step executes before test-runner."""
    ...
```

The hook accepts either placement. The regex for the ID is `[A-Z]{2,6}-[0-9]{3}`.

## Acceptance Criteria

```gherkin
Given check_test_ac_tags.py runs in warn mode against a staged test file
 Where a test function is missing a covers: tag
When the hook runs
Then it exits 0 (does not block the commit)
 And prints a warning listing the function name and file path

Given check_test_ac_tags.py runs in error mode against a staged test file
 Where a test function is missing a covers: tag
When the hook runs
Then it exits 1 and blocks the commit
 And the error message identifies the function name and file path

Given check_test_ac_tags.py runs against a staged test file
 Where all test functions have a valid covers: tag
When the hook runs
Then it exits 0 with no warnings or errors

Given a staged file is not a test file (does not match test_*.py)
When check_test_ac_tags.py processes it
Then the file is skipped silently

Given commit_guardian.json has test_ac_tag_enforcement: "warn"
When check_test_ac_tags.py reads the config
Then the hook runs in warn mode regardless of how it was invoked
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

### python-coder
- [ ] Write `templates/commit-guardian/check_test_ac_tags.py`:
  - Stdlib only (ast module for parsing test functions, re for tag search).
  - `is_test_file(path)` — returns True for `test_*.py` / `*_test.py`.
  - `find_test_functions(ast_tree)` — returns list of `(name, lineno)` for
    each `def test_*` function.
  - `has_covers_tag(source_lines, func_node)` — checks line above `def`,
    first line of body, and docstring for `# covers: XX-NNN` pattern.
  - `read_enforcement_mode(config_path)` — reads `commit_guardian.json`,
    returns `"warn"` or `"error"` (default `"warn"` if key absent).
  - main: iterate staged files, filter test files, check each function.
    Emit warnings or errors per enforcement mode. Exit 0 in warn mode
    always; exit 1 in error mode when violations found.
- [ ] Add `test_ac_tag_enforcement: "warn"` default to
  `templates/commit-guardian/commit_guardian.json`.
- [ ] Register `check_test_ac_tags.py` in `commit_guardian.json` hooks.

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_check_test_ac_tags.py`:
  - `test_tagged_function_passes` — function with `# covers: FIN-001` passes.
  - `test_untagged_function_warns_in_warn_mode` — exit 0, warning printed.
  - `test_untagged_function_blocks_in_error_mode` — exit 1.
  - `test_docstring_tag_accepted` — tag in docstring counts.
  - `test_non_test_file_skipped` — non-test files are ignored.
  - `test_no_test_functions_passes` — file with no test functions exits 0.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? New file. Fully reversible by removing from hook dispatch.
- The warn-first approach protects existing codebases from an immediate
  flood of blocked commits. The mode flag is in config, not hardcoded.
