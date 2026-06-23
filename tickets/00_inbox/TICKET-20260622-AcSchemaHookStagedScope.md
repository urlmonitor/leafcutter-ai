---
title: "Scope check-ac-schema hook to staged files instead of the whole store"
status: todo
components:
  - guardrail-engine
created: 2026-06-22
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/scripts/commit_guardian/check_ac_schema.py
  - unit_tests/commit_guardian/test_check_ac_schema.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Scope check-ac-schema hook to staged files instead of the whole store

## Actor / Goal

In order to keep the `check-ac-schema` pre-commit hook fast and relevant to the
commit at hand, the hook should validate only the AC YAML files that are actually
staged for the commit — not all files in the AC store on every commit — so that a
commit is never blocked or slowed by a pre-existing violation in an unrelated,
unstaged file.

## Context

### Background

This is **Bug 2** of the `check-ac-schema` regression diagnosed on 2026-06-22.
Bug 1 (the strict `validate_manually()` running on the jsonschema success path)
was fixed in PR #141 (AC GE-112, merge commit 120036d). This ticket tracks the
second, independent defect.

In `templates/scripts/commit_guardian/check_ac_schema.py`, `main()` calls
`_find_ac_files(root)` which does `sorted(ac_dir.rglob("*.yaml"))` — it validates
the **entire** AC store on every commit, regardless of what is staged. Combined
with `pass_filenames: false` in the hook registration, this means:

- Every commit pays the cost of validating the whole store.
- A pre-existing schema violation in any unstaged file blocks an otherwise-valid
  commit that does not touch that file.

The Phase 2 `implements_pattern` field-preservation check already demonstrates
the correct pattern: `_get_modified_ac_paths()` uses
`git diff --cached --name-only --diff-filter=M` to find staged AC files. Phase 1
(schema validation) should be scoped the same way — to staged AC YAML files only.

### Why this was split from the Bug 1 fix

The existing test suite in `unit_tests/commit_guardian/test_check_ac_schema.py`
drives the hook via `HOOK_ROOT` over a whole temp store **without git staging**.
Scoping Phase 1 to staged files would make the existing exit-1 tests
(`TestMissingRequiredField`, `TestInvalidStatus`, `TestInvalidIdFormat`,
`TestMalformedIdRejectedAfterWidening`, `TestUnknownFieldRejectedAfterWidening`,
`TestMissingRequiredFieldAfterWidening`, etc.) pass trivially (nothing staged →
nothing validated → exit 0). The test harness must be reworked to stage files
(or simulate staging via an env hook like the existing `HOOK_TEST_FILES_MODIFIED`
seam) before the scope change can land. That rework exceeds a single-file
quick-fix, hence this dedicated ticket.

## Acceptance Criteria

- [ ] AC-1: Phase 1 schema validation processes only AC YAML files that are
  staged for the current commit (staged-added or staged-modified under
  `docs/acceptance-criteria/`), determined via `git diff --cached`. Files present
  in the store but not staged are not validated in Phase 1.
- [ ] AC-2: A staged AC file that violates the schema still blocks the commit
  (exit 1) with the same per-file error reporting as today.
- [ ] AC-3: A commit that stages no AC YAML file exits 0 without scanning the
  store.
- [ ] AC-4: Cross-file pattern checks (`validate_pattern_bindings_completeness`,
  `validate_deprecated_pattern_reference`, `validate_criteria_not_pattern_duplicate`)
  continue to resolve referenced pattern ACs against the full on-disk store, so a
  staged consuming AC can still be checked against an unstaged pattern AC. Only
  the set of files that are *validated* is narrowed; the cross-file *lookup index*
  is not.
- [ ] AC-5: The hook remains fail-open — git unavailability or a `git diff`
  failure must not hard-block the commit.
- [ ] AC-6: The unit-test harness is reworked so the existing exit-1 schema tests
  exercise the staged-files path (e.g. via a staging simulation env var) rather
  than passing trivially because nothing is staged.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Out of Scope

- The Bug 1 fix (manual validator as fallback only) — already shipped in PR #141
  (AC GE-112).
- Changing the JSON Schema contract itself.

## Risk & Safety

- Touches money? No.
- Touches data? No — pre-commit validation only.
- Reversibility? High — the change is localized to file selection in `main()` /
  `_find_ac_files`.
- Risk of regressions: medium — the test-harness rework is the delicate part;
  the staged-file scoping must not silently stop validating genuinely-staged
  files. AC-6 exists specifically to guard against the "tests pass because
  nothing is staged" trap.
