---
title: "Register templates/commands/ in build parity test allow-list"
status: inbox
components:
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: low
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - tests/test_build_artifact_parity.py
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: trivial
ac_coverage: 0/2
---

# Register templates/commands/ in build parity test allow-list

## Actor / Goal

As a developer maintaining the build pipeline, I need the build parity test
suite to pass on main so that CI is green and pre-existing failures do not
mask new regressions.

## Context

Commit 80149f7 added `templates/commands/` (slash command definitions for
`/po`, `/ba`, `/it-po`) but did not update the build parity test's
directory allow-list.

`TestTemplateDirectoriesHaveCategories.test_no_unlisted_artifact_template_dirs`
iterates every directory under `templates/` and asserts it is either in
`_USER_FACING_CATEGORIES`, `_INTERNAL_CATEGORIES`, or the `non_artifact_dirs`
exemption set. Because `commands` appears in none of those three sets, the
test fails with:

```
AssertionError: Template directory 'commands' exists but is not listed in
test_build_artifact_parity.py.
```

`templates/commands/` holds static slash-command markdown files. It does not
produce shimmed build outputs and does not need shim_map, managed-artifact-dir,
or drift-detection coverage. The correct fix is to add `"commands"` to
`non_artifact_dirs` — one line, no other changes required.

333 other tests pass. This is the only failing test on main.

## Acceptance Criteria

- [ ] AC-1: `"commands"` is present in the `non_artifact_dirs` set inside
  `TestTemplateDirectoriesHaveCategories.test_no_unlisted_artifact_template_dirs`
  in `tests/test_build_artifact_parity.py`.
- [ ] AC-2: Running `python -m pytest tests/test_build_artifact_parity.py -v`
  reports 6 passed, 0 failed, with all subtests green including
  `test_no_unlisted_artifact_template_dirs`.

## AC Coverage

| AC   | Test | Implementation | Validated |
|------|------|----------------|-----------|
| AC-1 |      |                |           |
| AC-2 |      |                |           |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
