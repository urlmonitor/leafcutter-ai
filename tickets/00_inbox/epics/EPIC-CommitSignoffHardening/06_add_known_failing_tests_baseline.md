---
title: "Add known-failing-tests baseline so commits only block on net-new test failures"
status: todo
components:
  - build_system
created: 2026-05-22
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - scripts/commit_guardian/known_failing_tests.json
  - scripts/commit_guardian/commit_guardian.json
  - .pre-commit-config.yaml
agents:
  architect-review: not_needed
  python-coder: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  test-writer: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  sql-coder: not_needed
  user-surface-smoker: not_needed
---

# 06: Add known-failing-tests baseline so commits only block on net-new test failures

## Actor / Goal

In order to eliminate the `--no-verify` escape path that users reach for when pre-existing test failures block unrelated commits, the pre-commit test hook must diff current failures against a maintained baseline file and block **only** on failures that are not already recorded in the baseline.

## Context

Feedback sources: general pattern observed across the feedback corpus — when `pytest` discovers pre-existing failures (tests that were already failing before the current change), the pre-commit hook blocks the entire commit. Users who are not responsible for those failures reach for `--no-verify` to ship their own unrelated work. This erodes hook discipline across the board.

The `--no-verify` escape path is the most harmful hygiene gap in the commit pipeline: it bypasses ALL hooks, not just the failing test check.

The root cause is that the pre-commit test hook applies a binary pass/fail against the full test suite, with no concept of "previously known failing". Any pre-existing failure, however unrelated, becomes a blocker.

The fix: maintain a baseline file (`scripts/commit_guardian/known_failing_tests.json` — confirm exact path during refinement) that lists tests currently known to be failing. The pre-commit hook diffs current failures against the baseline and blocks only on **new** failures (those present in current run but absent from the baseline). Baseline updates are an explicit, reviewable `git add` action, not a side-effect of running tests.

## Acceptance Criteria

```gherkin
Given a test that is listed in the known-failing baseline is still failing
When the pre-commit test hook runs
Then the hook exits 0 for that test (it is a known failure, not a new regression)
And the commit proceeds normally

Given a test that is NOT listed in the baseline fails
When the pre-commit test hook runs
Then the hook exits 1 and reports the new failure
And the commit is blocked with an actionable error identifying the new failing test(s)

Given a developer wants to update the baseline (acknowledging a new known-failing test)
When they run the baseline-update command
Then the baseline file is updated and the change is staged as a reviewable git diff
And a subsequent commit with the same failure is no longer blocked

Given the baseline file does not exist
When the pre-commit test hook runs
Then the hook treats all failures as new (same behaviour as no-baseline mode)
And exits 1 if any tests fail
```

## Sign-offs

- [ ] python-coder
- [ ] documentation-expert
- [ ] test-writer
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Locked Approach

**Hook candidate: pre-commit test hook with baseline diffing.**

The pre-commit hook that runs the test suite is modified to:

1. Collect the set of currently failing test node IDs from the `pytest` run (via `--tb=no -q` or JSON report).
2. Load `scripts/commit_guardian/known_failing_tests.json` (if it exists). The baseline is a JSON object:
   ```json
   {
     "baseline_date": "YYYY-MM-DD",
     "known_failing": [
       "unit_tests/foo/test_bar.py::test_something",
       "unit_tests/baz/test_qux.py::test_another"
     ]
   }
   ```
3. Compute `new_failures = current_failures - known_failing_set`.
4. If `new_failures` is empty: exit 0 (all failures are baseline-known; commit proceeds).
5. If `new_failures` is non-empty: exit 1, reporting only the new failures.

A companion CLI command (e.g. `python scripts/commit_guardian/known_failing_tests.py --update`) regenerates the baseline from the current failing test set. This command is the only way to update the baseline — the hook never writes to it automatically.

Confirm the exact file path (`scripts/commit_guardian/known_failing_tests.json`) during refinement by checking for an existing test-hook entry in `commit_guardian.json`.

## Implementation Tasks

### python-coder
- [ ] Read `scripts/commit_guardian/commit_guardian.json` and identify the hook entry that runs pytest at pre-commit time. Note the exact `hook_id`, script path, and any existing failure-handling logic.
- [ ] Implement the baseline file schema (`known_failing_tests.json`) and a loader function that returns a `frozenset` of test node IDs. If the file is absent or malformed, return an empty set (fail-open: treat all failures as new).
- [ ] Modify the pre-commit test hook script to:
  - Run pytest and collect failing test node IDs.
  - Load the baseline.
  - Compute the diff and exit 0 or 1 accordingly.
  - On exit 1, print the new failures clearly and include a hint: "To acknowledge these failures as baseline, run: `python scripts/commit_guardian/known_failing_tests.py --update`".
- [ ] Implement the `--update` CLI subcommand: run pytest, collect all current failures, write them to the baseline file with the current date, and print the path of the updated file.
- [ ] Register any new script in `commit_guardian.json` and `.pre-commit-config.yaml` at the correct stage.

### documentation-expert
- [ ] Write or update a how-to in `docs/how-to/` explaining the baseline workflow:
  - When to update the baseline (acknowledging a pre-existing failure that is not yours to fix in this PR).
  - How to update it (`--update` command).
  - Policy: baseline entries must not accumulate indefinitely — link to the epic ticket for any entry older than 30 days.
- [ ] Add a note in `.claude/agents/commit.md` referencing the baseline approach so commit agents do not reach for `--no-verify` when tests fail.

### test-writer
- [ ] Write a unit test in `unit_tests/commit_guardian/` that:
  - Mocks a pytest run returning `{test_A, test_B}` as failures.
  - Sets the baseline to `{test_A}`.
  - Asserts the hook exits 1 and reports only `test_B`.
- [ ] Write a test where all current failures are in the baseline — assert hook exits 0.
- [ ] Write a test where the baseline file is absent — assert hook exits 1 if any tests fail (fail-open).
- [ ] Write a test for the `--update` command: after running it, the baseline file contains the current failing set.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Removing the baseline file or the diffing logic reverts to prior all-or-nothing behaviour. The baseline file itself is tracked in git, so any update is reviewable and revertable.
- Risk of misuse: the baseline mechanism must NOT become a dumping ground for ignored failures. The `--update` command produces a reviewable diff (the baseline file changes appear in `git diff`), so the PR review step acts as a gate on baseline growth.
- The hook must still run pytest — it must not skip the test run. The baseline only affects how failures are reported, not whether tests run.
