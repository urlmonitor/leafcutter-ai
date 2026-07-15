---
title: "Backfill green test coverage for BP-600 (quick-fix-workflow) ACs"
status: todo
components:
  - build_pipeline
created: 2026-07-15
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
test_required: true
source_ac: BP-600a-1
ac_coverage:
  - BP-600a-1
  - BP-600a-2
  - BP-600a-3
  - BP-600a-3-i
  - BP-600b-1
  - BP-600b-2
  - BP-600b-2-i
  - BP-600b-3
  - BP-600c-1
  - BP-600c-2
  - BP-600c-3
  - BP-600d-1
  - BP-600d-1-i
  - BP-600d-2
  - BP-600d-3
  - BP-600d-4
  - BP-600d-4-i
  - BP-600e-1
  - BP-600e-2
  - BP-600e-3
  - BP-600e-3-i
files_touched:
  - unit_tests/workflows/test_quick_fix_workflow.py
  - templates/workflows-js/quick-fix.js
  - templates/skills/quick-fix/SKILL.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 02: Green test coverage for BP-600 (quick-fix-workflow)

## Actor / Goal

As the AC store, I want every BP-600 AC in `ac_coverage` to have a real, green unit
test that **names the AC** (`# covers: <AC>`), so its `work_status: done` is honestly
backed by verifiable coverage (per the 2026-07-14 test-truth rule).

## Test Backfill Context

**Nature: CODE_NO_TEST.** Per the 2026-07-14 audit, the entire quick-fix workflow is
implemented in `templates/workflows-js/quick-fix.js` + `templates/skills/quick-fix/SKILL.md`
and has **ZERO tests today**. **Do NOT rewrite the workflow code.** Author asserting tests
that cover the 21 CODE_NO_TEST leaves. (The four real gaps b-1-i, c-2-i, c-3-i, e-1-i are
NOT_IMPLEMENTED and are deliberately excluded from this ticket.)

The surfaces under test (read-only):
- `templates/workflows-js/quick-fix.js` (the workflow control flow)
- `templates/skills/quick-fix/SKILL.md` (the skill contract/prose)

**Testing approach note:** quick-fix.js is a JavaScript workflow, so a pure Python unit
test cannot exercise its runtime directly. Cover these ACs by asserting the workflow
**source contract** — parse `quick-fix.js` / `SKILL.md` and assert the presence and shape
of the control-flow branches, dispatch calls, guard clauses, and prose the criteria
require (e.g. "never dispatches worktree-agent", "dispatches test-writer before fix",
"halts when target file has uncommitted changes"). Where a behavioural/replay harness is
feasible for a branch, prefer it; otherwise a source-contract assertion is acceptable for
a prose/config surface. Each test must still name its AC and make a genuine assertion (not
a `hasattr`/existence-only check).

## What each test must assert

Read each AC's `criteria` in
`docs/acceptance-criteria/build_pipeline/BP-600-quick-fix-workflow/<AC>.yaml`. Summary:

- **BP-600a-1** — all operations run in the current worktree; branch unchanged before/after;
  no new worktree dir created.
- **BP-600a-2** — never dispatches worktree-agent, never invokes the feature skill, never
  calls `git worktree add`.
- **BP-600a-3** — halts before any change when the *target* file has uncommitted changes;
  reports the conflict; suggests commit/stash.
- **BP-600a-3-i** — proceeds when only *unrelated* files are dirty; does not stage/commit them.
- **BP-600b-1** — creates an AC YAML under `docs/acceptance-criteria/` with id/title/component/
  status:active/criteria (Given-When-Then) describing the bug.
- **BP-600b-2** — new AC uses the component prefix from index.yaml + next sequential id
  (no reuse).
- **BP-600b-2-i** — infers component from the diagnosed file path via index.yaml; asks the
  user when no mapping.
- **BP-600b-3** — the AC file persists (status active) after the ticket lifecycle closes.
- **BP-600c-1** — dispatches test-writer with the AC; produced test reproduces the bug and
  carries `# covers: <AC-ID>`, written before any fix code.
- **BP-600c-2** — runs the new test and confirms RED; halts with the specified warning if it
  unexpectedly passes.
- **BP-600c-3** — reruns the same test after the fix and confirms GREEN; halts with the
  specified warning if still failing.
- **BP-600d-1** — parses a structured diagnosis into file/location/symptom/root-cause and
  drives subsequent phases from those fields.
- **BP-600d-1-i** — rejects input lacking a file path or root cause with the structured
  three-part prompt; does not proceed to AC creation.
- **BP-600d-2** — dispatches python-coder with diagnosis + failing test + target; coder
  modifies only the target file.
- **BP-600d-3** — dispatches the commit agent (never `git commit` directly); stages only the
  quick-fix files; commit message references the AC id.
- **BP-600d-4** — pushes to the branch remote; updates the existing PR if present; creates/
  updates a minimal ticket with status:done + AC id reference.
- **BP-600d-4-i** — when no PR exists: pushes but does not create one; reports the exact
  message; still closes the ticket with status:done.
- **BP-600e-1** — pauses before green phase with the "modified N files (expected 1)" warning
  and waits for confirmation when ≥2 source files change.
- **BP-600e-2** — pauses with the "root cause may differ" warning when the red failure points
  elsewhere; waits for confirmation.
- **BP-600e-3** — on escalation, preserves the created AC + test file, outputs a summary
  (AC id, test path, file, root cause) and the AC id for /build-feature.
- **BP-600e-3-i** — on escalation after the fix but before commit: commits nothing; AC/test/
  fix remain unstaged; user is told which files are preserved.

## Acceptance Criteria

For each AC in `ac_coverage`: a green test names it (`# covers: <AC>`) and asserts its
behaviour/contract; its `covered_by` records the test path (`::test_function`);
`work_status: done` only after green (mark-done is a follow-up).

## Test Requirements

```yaml
tests:
  - name: test_bp600_quick_fix_workflow
    file: unit_tests/workflows/test_quick_fix_workflow.py
    covers: [BP-600a-1, BP-600a-2, BP-600a-3, BP-600a-3-i, BP-600b-1, BP-600b-2, BP-600b-2-i, BP-600b-3, BP-600c-1, BP-600c-2, BP-600c-3, BP-600d-1, BP-600d-1-i, BP-600d-2, BP-600d-3, BP-600d-4, BP-600d-4-i, BP-600e-1, BP-600e-2, BP-600e-3, BP-600e-3-i]
    asserts: >
      Each listed AC has at least one green test naming it that asserts the corresponding
      quick-fix.js / quick-fix SKILL control-flow branch, dispatch call, guard clause, or
      documented contract required by that AC's criteria (source-contract assertion, or a
      behavioural/replay harness where feasible).
```

## Sign-offs

- [ ] test-writer
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
