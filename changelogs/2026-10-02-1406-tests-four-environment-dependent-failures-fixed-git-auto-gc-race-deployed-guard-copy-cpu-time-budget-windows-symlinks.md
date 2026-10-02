---
title: "Tests: four environment-dependent failures fixed (git auto-gc race, deployed guard copy, CPU-time budget, Windows symlinks)"
date: "2026-10-02"
time: "14:06"
type: manual
components: 
  - testing_quality
  - commit_guardian
summary: "Four tests that failed for reasons unrelated to the code they guard now pass reliably on CI and on Windows, and each still fails on the real problem it is meant to catch. Three tickets record tooling defects found along the way."
description: "test_ge_127e_4 and its GE-127e siblings raced git's background packing: the shared snapshot now ignores .git/objects and the shared init_repo disables auto-gc and maintenance; a leaked file in the working tree or elsewhere in .git still fails. test_ge_122e_1 counted the gitignored deployed copy of the contract-shrinking guard (present only after build.py) as a live GE-119 citation; it is now exempted like the template source. test_ge_122a_1's 8-second wall-clock budget measured machine load (about 1s CPU against 20-25s wall on a busy Windows box); it now bounds CPU time at 5s, and an injected 30s CPU regression still fails. test_bp_900h6i/ii needed privileged symlinks on Windows: the test whose subject is the symlink skips via a real capability probe, the two incidental links fall back to directory junctions. Tickets added: commit agent's machine-wide pytest kill, worktree bootstrap leaving tracked files modified, and the glossary hook's standalone stub that would blacklist every new term."
---

## Entry

### Changed

- `unit_tests/commit_guardian/_ge_127e_1_fixture.py`, `_ge_127e_3_fixture.py`,
  `test_ge_127e_4_reachability_and_deployed.py` — no race with git background packing.
- `unit_tests/commit_guardian/test_ge_122e_1.py` — the deployed guard copy is exempt.
- `unit_tests/commit_guardian/test_ge_122a_1.py` — CPU-time budget instead of wall-clock.
- `unit_tests/portability/test_bp_900h6i.py`, `test_bp_900h6ii.py` — symlink capability probe and
  junction fallback.

### Added

- Three tickets in `tickets/00_inbox/` (commit agent pytest kill, worktree bootstrap dirty files,
  glossary hook stub).
