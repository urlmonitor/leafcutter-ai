---
title: "Create the missing check_ac_done_on_merge hook (test_check_ac_done_on_merge)"
status: todo
components:
  - commit_guardian
created: 2026-07-15
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
files_touched:
  - templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py
  - tests/commit_guardian/test_check_ac_done_on_merge.py
agents:
  test-writer: not_needed
  python-coder: needed
  test-runner: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Create the missing check_ac_done_on_merge hook

## Actor / Goal

As a maintainer, I want the `check_ac_done_on_merge` hook to actually exist and behave
per its test, so `test_check_ac_done_on_merge` (AC ACD-600b) goes green instead of
erroring on a nonexistent script.

## Context

`tests/commit_guardian/test_check_ac_done_on_merge.py` has **3 failures** (masked to
xfail on CI). Root cause (verified with `-o addopts=""`): the test invokes
`.../scripts/commit_guardian/hooks/check_ac_done_on_merge.py`, which raises
`[Errno 2] No such file or directory` — **the hook script does not exist anywhere in the
repo** (only `hooks/check_agent_spawn_consistency.py` is present). This is genuinely
unimplemented code, not a stale test. No epic or the salvage owns it.

Note the source-of-truth path: hooks are authored under `templates/scripts/commit_guardian/`
and deployed to `scripts/commit_guardian/` by `build.py`. Author the hook in the template
tree; verify the test resolves it via the deployed path after build (the test may need
the deployed shim — coordinate with how sibling hooks are tested).

## Acceptance Criteria

```gherkin
Given a merge that marks ACs done
When check_ac_done_on_merge runs
Then it implements the behavior test_check_ac_done_on_merge asserts (AC ACD-600b)
  and the test passes with addopts="" AND under AC_ENFORCE_STRICT=1

Given the implementation
Then the hook enforces the real ACD-600b invariant (it actually blocks/acts on the
  merge condition it is meant to guard) — verified by exercising the hook against a
  real staged scenario, not by trimming the test to match a stub
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | tests/commit_guardian/test_check_ac_done_on_merge.py | templates/scripts/commit_guardian/hooks/check_ac_done_on_merge.py | |

## Test Requirements

```yaml
tests:
  - name: test_marks_done_for_source_ac_tickets
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    covers: [ACD-600b]
    asserts: the check_ac_done_on_merge hook marks source-AC tickets done on merge (happy path).
  - name: test_skips_tickets_without_source_ac
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    covers: [ACD-600b]
    asserts: the hook skips tickets that have no source AC.
  - name: test_hook_exits_0_on_mark_failure
    file: tests/commit_guardian/test_check_ac_done_on_merge.py
    covers: [ACD-600b]
    asserts: the hook fails soft (exit 0) when a mark operation fails, rather than blocking the merge.
```

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks

- [ ] Read `test_check_ac_done_on_merge.py` to extract the exact contract (args, exit
      codes, stdout/stderr, the merge condition it guards) and the AC ACD-600b text.
- [ ] Implement the hook under `templates/scripts/commit_guardian/hooks/` following the
      error-handling policy (typed except, log-or-raise) and sibling-hook conventions.
- [ ] Register it in `commit_guardian.json` hooks_manifest if the test/behavior requires it.
- [ ] Confirm the test passes with `-o addopts=""` and `AC_ENFORCE_STRICT=1`.

## Risk & Safety
- Touches money? No.
- Touches data? No — adds a commit-guardian hook; behavior gated by tests.
- Reversibility? Fully reversible.
