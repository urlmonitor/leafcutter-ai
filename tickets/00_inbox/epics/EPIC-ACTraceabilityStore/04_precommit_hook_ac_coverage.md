---
title: "Pre-commit hook: every active AC must appear in at least one test's covers tag"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
  - 03_precommit_hook_test_tagging.md
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/commit-guardian/check_ac_coverage.py
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

# 04: Pre-commit hook: every active AC must appear in at least one test's covers tag

## Actor / Goal

In order to prevent ACs from going untested after they are created or amended,
we need a pre-commit hook that scans all active ACs in `docs/acceptance-criteria/`
and verifies each one appears in at least one `# covers:` tag across the test
suite, so that newly created ACs without tests are flagged at commit time.

## Context

This is the reverse direction of ticket 03. Ticket 03 checks that tests point
to ACs. This ticket checks that ACs are pointed to by tests. Together, they
enforce bidirectional coverage.

The check is asymmetric in severity:
- Missing `covers:` tag on a test (ticket 03) → configurable warn/error.
- Active AC with no test coverage (this ticket) → **warning only, always.**
  The warning is a prompt to the author to write a test; it is not a block,
  because the AC may have been created in a ticket that expects `test-writer`
  to add coverage in the same build cycle.

The hook works by:
1. Reading all `.yaml` files in `docs/acceptance-criteria/**/*.yaml`.
2. Filtering to `status: active` ACs.
3. Scanning all test files in `unit_tests/**/*.py` for `# covers: XX-NNN` tags.
4. For each active AC ID not found in any `covers:` tag: emit a warning.

### Performance

The hook scans the full test suite on every commit. For large repos with many
tests, this may be slow. The implementation should use a simple `grep`-style
scan (stdlib `re`) rather than full AST parsing to keep it fast.

## Acceptance Criteria

```gherkin
Given an active AC with ID FIN-001 exists in docs/acceptance-criteria/
 And no test file contains # covers: FIN-001
When check_ac_coverage.py runs
Then it prints a warning: "AC FIN-001 has no test coverage"
 And exits 0 (does not block the commit)

Given an active AC with ID FIN-001 exists
 And at least one test file contains # covers: FIN-001
When check_ac_coverage.py runs
Then no warning is emitted for FIN-001

Given an AC with status: deprecated exists
 And no test file covers it
When check_ac_coverage.py runs
Then no warning is emitted for the deprecated AC

Given docs/acceptance-criteria/ does not exist in the target project
When check_ac_coverage.py runs
Then it exits 0 silently (hook degrades gracefully when store not yet installed)
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
- [ ] Write `templates/commit-guardian/check_ac_coverage.py`:
  - Stdlib only (re, yaml if available; manual YAML parse for `id:` and
    `status:` if yaml not installed).
  - `load_active_ac_ids(ac_dir)` — recursively glob `*.yaml`, parse `id`
    and `status`, return set of IDs where `status == "active"`.
  - `collect_covered_ids(test_dir)` — recursively glob `test_*.py` and
    `*_test.py`, scan for `# covers: XX-NNN` regex, return set of found IDs.
  - `report_uncovered(active_ids, covered_ids)` — print warnings for each
    `active_ids - covered_ids`.
  - Graceful degradation: if `docs/acceptance-criteria/` does not exist,
    exit 0 with no output.
  - Always exit 0 (warnings only, never block).
- [ ] Register `check_ac_coverage.py` in `commit_guardian.json` hooks
  (pass_filenames: false, no file filter — runs on every commit).

### test-writer
- [ ] Write `unit_tests/commit_guardian/test_check_ac_coverage.py`:
  - `test_uncovered_active_ac_warns` — active AC with no test coverage prints warning.
  - `test_covered_ac_passes_silently` — active AC with coverage emits no warning.
  - `test_deprecated_ac_ignored` — deprecated AC with no coverage emits no warning.
  - `test_missing_ac_dir_exits_0` — no docs/acceptance-criteria/ → exit 0.
  - `test_multiple_uncovered_acs_all_warned` — three uncovered ACs → three warnings.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? New file. Removing from hook dispatch restores prior behaviour.
- Warning-only ensures the hook never blocks a commit. Teams can iterate
  on AC creation and test coverage in the same feature branch without friction.
