---
title: "KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run — a real-git fixture's teardown races its own `.git/objects` and fails a suite in which every assertion passed"
description: "medium — it costs a full CI cycle and, worse, presents as a defect in whatever"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
---

# KI-TQ-20260914-tempdir-cleanup-race-fails-a-green-test-run — a real-git fixture's teardown races its own `.git/objects` and fails a suite in which every assertion passed

> One known issue, split out of `docs/known-issues/testing-quality.md` on
> 2026-09-14. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — it costs a full CI cycle and, worse, presents as a defect in whatever
  change is on the branch
- **Status:** open. Reproduced once in CI on PR #794; the same commit re-run passed unchanged.
  Passes locally on repeated runs.
- **Occurrences:** 1 observed (2026-09-14); expected to recur, since the cause is a race
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `unit_tests/commit_guardian/test_ge_127a_1_i_entry_points.py` —
  `TestDeployedCopyFailsClosedOnUnmeasurableFile::test_ge_127a_1_i_the_deployed_copy_fails_closed_on_an_unmeasurable_file_in_a_cold_process`;
  the `tempfile.TemporaryDirectory` teardown, via `shutil._rmtree`

**Symptom.** The suite reports `1 failed, 5914 passed` — and the one failure is not an assertion:

```
OSError: [Errno 39] Directory not empty: '/tmp/tmpftvu8oaf/.git/objects'
  File ".../shutil.py:658", in _rmtree
    self._rmtree(self.name, ignore_errors=self._ignore_cleanup_errors)
```

Every assertion in the test passed. The failure is the `TemporaryDirectory` context manager
failing to delete a real git repository the fixture created, because something was still writing
into `.git/objects` while `rmtree` walked it — git's own background housekeeping, or a not-yet-
reaped child process.

**Why it matters more than an ordinary flake.** It is attributed to the branch. On PR #794 the
change under test was the deletion of two unrelated hook scripts, and the failure named a
file-size gate test; the honest response is to stop and investigate, and the cost is a full
re-run of a 17-minute suite before it can be dismissed. A flake that fails in teardown rather
than in an assertion is also easy to misread as a genuine defect, because the test name in the
`FAILED` line is a real test.

**Cause, narrowed.** This family of tests is new: `GE-127a-1` (PR #728) introduced fixtures that
build a temp git repo, run a real `pre-commit install`, and drive a real `git commit`, precisely
so the gate is exercised through the commit path rather than by hand. That is the right shape —
it is the fix for `KI-TQ-007`'s own lesson — but it means the tests now own live git repositories,
and a live git repository is not reliably deletable the instant the last command returns.

**Fix direction.** Pass `ignore_cleanup_errors=True` to the `TemporaryDirectory` in these fixtures
(Python 3.10+, and this repo runs 3.13). A cleanup failure in a temp directory is not a test
result and must not be reported as one; the OS reclaims `/tmp` regardless. If the leak itself is
a concern, reap child processes explicitly before teardown rather than making the deletion a
pass/fail condition. Apply to every fixture in `commit_guardian` that creates a real git repo —
`_ge_127a_1_ordinary_commit_fixture.py` and `_ge_127c_1_scope_fixture.py` have the same shape.

**Pattern:** teardown reported as a test outcome, so an environment race is indistinguishable from
a defect in the change under test.
