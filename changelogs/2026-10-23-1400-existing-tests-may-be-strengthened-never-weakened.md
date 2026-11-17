---
title: "Existing tests may be strengthened but never weakened: before every commit a sweep stops unlisted edits, tests that stopped passing, and changed tests that now assert less"
date: "2026-10-23"
time: "14:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "wrong_version_gate.py finish now runs a consumer-test sweep (consumer_sweep.py check) before the wrong-version runs and stops the work at 'sweep' when an edit to an existing test or conftest.py was not recorded by the test writer, when an existing test that passed at the base is now skipped, expected to fail or gone, or when a changed existing test asserts less, compares more loosely, tolerates more, or has an assertion made conditional or unreachable. The test writer records the existing tests it strengthened or removed (consumer_sweep.py record) once after its last edit."
description: "TQ-500g-3, TQ-500g-3-i, TQ-500g-3-ii, TQ-500g-3-iii. -i: consumer_sweep.py record/check with _cs_edits.py and _cs_symbols.py (every top-level statement of a test file is a symbol; raw-byte compare for non-.py files; lists bound to the work's base commit; fingerprints computed by record; fail-closed on unreadable sources and internal errors). -ii: _cs_runs.py runs the changed existing test files on an export of the base (git archive, symlinks dropped, removed in finally) and on the working tree; PASSED at base -> skipped (incl. module-level skip) / expected to fail / gone is weakened; a 'removed' entry with a note excuses only a deletion; a changed conftest.py or a pytest config at or above the test root widens the runs. -iii: _cs_asserts.py and _cs_guards.py compare the AST of each changed test: fewer assertions, a lost or loosened strict comparison per subject, a wider pytest.approx tolerance, and (rule d, user decision 2026-10-23) an assertion moved under a condition or behind a new early return/skip/xfail. Prompt: templates/agents/test-writer.md Existing-Test Sweep section. User decisions Q1-Q4 (2026-10-22); known gaps (dropped match=, wider places/delta, a loose form made looser, a widened expected literal) are left to pr-reviewer. Review findings fixed test-first; wrong-version gates passed for all three children."
commits:
breaking: false
---

## Entry

A test writer could quietly weaken an existing test so that a change passes. The analysis
found this happening. Before every commit the build now checks the existing tests the work
touched. Any edit the test writer did not record stops the work, and so does a test that
used to pass and is now skipped or gone. A changed test that now checks less also stops it,
even when the writer listed it as strengthened.
