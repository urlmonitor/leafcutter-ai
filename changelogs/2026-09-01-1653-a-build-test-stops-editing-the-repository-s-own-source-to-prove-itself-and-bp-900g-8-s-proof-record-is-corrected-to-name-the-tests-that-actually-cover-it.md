---
title: "A build test stops editing the repository's own source to prove itself, and BP-900g-8's proof record is corrected to name the tests that actually cover it"
date: "2026-09-01"
time: "16:53"
type: manual
components: 
  - build_pipeline
  - ac_store
summary: "A test that checks the build correctly blocks a broken deploy no longer edits real source code to prove it, closing off a way an interrupted or concurrent test run could leave a tracked file corrupted, and the record of which tests prove that requirement now names the tests that actually do."
description: "test_bp_900g_8 proved the build's closure guard by editing scripts/build_phases.py in place and restoring it in a finally block; an interrupt, crash, or a concurrent session sharing the worktree could have left that tracked file mutated. It now withholds against a shutil.copytree scratch copy instead, reusing the helper test_bp_100k_2.py already provides and that test_bp_900g_9.py already uses for the same class of deploy-map mutation, so nothing tracked is written. What the test proves was verified rather than assumed: re-mutating the guard at build.py:1925 into 'if False and ...' still made the test fail as required, confirming it remains the only test that catches the guard being disconnected from the build, before being restored and re-run green. Separately, BP-900g-8 was work_status: done with covered_by naming only three child ACs, each themselves todo with covered_by: [] -- an unfinished proof chain that proved nothing, while 18 real tests already carrying its covers-tag (7 in test_bp_900g_8.py, 11 in test_bp_closure_guard_correctness.py) went unrecorded. Both files are now listed in covered_by alongside the preserved child ids. work_status was left untouched: this corrects the record of what already proves the requirement, not the requirement's status."
commits: 
  - be55a9417
  - 0e37b160e
breaking: false
---

## Entry

Two independent findings landed on this branch. Neither changes product behaviour — one removes a way the test suite could corrupt a working tree; the other makes a requirement honest about its evidence.

### The test that edited real source to prove itself

`test_bp_900g_8_build_subprocess_blocks_when_a_resolved_dependency_is_withheld_from_the_deploy` proved that the build correctly blocks a deploy when a resolved dependency is withheld — by editing this repository's own tracked `scripts/build_phases.py` **in place**, then restoring it in a `finally` block. That is the risk worth leading with: an interrupt, a crash, or a concurrent session sharing the worktree could have left a tracked source file mutated, in a repo that routinely runs agent fleets across shared worktrees.

The withholding now happens against a `shutil.copytree` scratch copy of the package instead, via the `_build_synthetic_full_package()` helper that `unit_tests/build_guards/test_bp_100k_2.py` already provides and that `test_bp_900g_9.py` already uses for the identical class of deploy-map mutation. No new pattern was invented, and nothing tracked is written, so no crash-safe restore is needed.

The part worth the most words: **what the test proves was verified unchanged, not assumed.** Before trusting the refactor, the guard at `build.py:1925` was deliberately re-mutated to `if False and _check_intra_package_closure_guard(...)` — and the test still failed as required, confirming it remains the only test that catches this guard being disconnected from the build. It was then restored and re-run green. A refactor that quietly removed the hazard by removing the guard's only test would have been strictly worse than the hazard it set out to fix.

### The proof record that named nothing

`BP-900g-8` read `work_status: done`, with `covered_by` naming only three child ACs — `BP-900g-8-i`, `-ii`, `-iii` — each of them themselves `work_status: todo` with `covered_by: []`. The declared proof chain was a chain of unfinished records, proving nothing. Meanwhile 18 real tests already carrying its `# covers: BP-900g-8` tag — 7 in `test_bp_900g_8.py`, 11 in `test_bp_closure_guard_correctness.py` — went entirely unrecorded. Both failure modes were present at once: the recorded proof was absent, and the real proof was unrecorded.

Both test files are now listed in `covered_by`, alongside the three preserved child ids. To be precise about what this is: it **corrects the record of what already proves the requirement** — those 18 tests existed and were passing before this change; nothing about them became newly proven.

`work_status` was deliberately left at `done` rather than reopened. The decisive test its criteria still name as outstanding belongs to `BP-900g-8-i`, which is openly `todo` — so the store already represents that gap on its own terms, and touching `work_status` here would have conflated two separate questions.
