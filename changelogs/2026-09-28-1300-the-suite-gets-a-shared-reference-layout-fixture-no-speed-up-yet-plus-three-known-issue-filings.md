---
title: "The suite gets a shared reference layout fixture; no speed-up yet, plus one known issue filed and two corrected"
date: "2026-09-28"
time: "13:00"
type: manual
components: 
  - testing_quality
  - commit_guardian
summary: "Test infrastructure now has a mechanism to share one deployed build across tests instead of every test rebuilding its own, though none of the 77 existing slow tests have been switched over yet; separately, three known-issue records were filed or corrected to keep the team's defect list accurate."
description: "TQ-600a-1 (e2d9cd0d) adds scripts/suite_performance/: a session-scoped pytest fixture (shared_reference_layout) that produces one build.py --target-dir deployment per run behind a cross-process lock and hands it to every consuming test, plus a CLAUDE.md rule directing new read-only tests to it instead of spawning their own build. 7 tests, green under AC_ENFORCE_STRICT=1. This ships the mechanism only: none of the 77 existing build.py --target-dir call sites (52 files, 63% of the suite's 1:29:47 local / 32-49min CI wall clock) are migrated by this commit; that migration is TQ-600a-2 through a-5, and parallel execution is TQ-600b-5 -- no measurable suite speed-up is claimed here. Also splits docs/testing/test-angles.md's failure catalogue into a cross-linked sibling doc for the doc-length ratchet, and adds two glossary entries plus one blacklist row. 9513a0aa files one new known issue -- a worktree's first commit rewrites the deployed commit_guardian.json, so check-output-drift refuses every later commit in that worktree -- and reconciles two existing ones: KI-CG-20260909-gate-root-files marked partially resolved (PR #857 fixed its M-matching half), and KI-BP-016's occurrence count raised with the note that build.py --force is now refused by the permission layer."
commits: 
  - e2d9cd0d
  - 9513a0aa
breaking: false
---

## Entry

**User-visible: the shared reference layout fixture (TQ-600a-1).** `scripts/suite_performance/`
now provides a session-scoped pytest fixture, `shared_reference_layout`, that produces one
deployed `build.py --target-dir` layout per test run (behind a cross-process lock, so
parallel workers wait for and share the same root instead of racing to build their own) and
hands it to any test that only needs to read a deployed layout. A `get_or_produce_shared_layout()`
entry point covers callers outside fixture context. `pytest.ini` registers it whole-suite via
`addopts`, alongside the existing AC-enforcement plugin. A new CLAUDE.md rule tells test
authors to request the fixture instead of spawning their own build; tests that mutate the
package before building (and assert the build fails) keep their own copy, since sharing would
corrupt the shared root for every other consumer. 7 tests are green under
`AC_ENFORCE_STRICT=1`.

**Be clear about what this does not yet do.** This ships the mechanism only — no measurable
suite speed-up is claimed. A full run still measures 1:29:47 locally (32-49 min in CI), with
63% of that wall clock sitting in 60 of 5318 tests, each spawning its own real
`build.py --target-dir` subprocess at 59.8s a piece. There are 77 such call sites across 52
test files, and this commit migrates none of them — that is TQ-600a-2 through TQ-600a-5, and
parallel execution is TQ-600b-5. Also included: `docs/testing/test-angles.md`'s failure
catalogue split into a cross-linked sibling doc to satisfy the doc-length ratchet, plus two
glossary entries and one blacklist row for the new surface.

**Internal record-keeping: known-issues bookkeeping.** One new entry is filed —
`KI-CG-20260928-first-commit-leaves-the-deployed-config-drifted` (high) — because a worktree's
first commit rewrites the deployed `commit_guardian.json`, so `check-output-drift` passes on
that commit and then refuses every later commit in the same worktree. Two existing entries are
reconciled: `KI-CG-20260909-gate-root-files` is marked partially resolved, since PR #857 fixed
its `M`-matching half (the allowlist half is still open); and `KI-BP-016`'s occurrence count
is raised, with the added note that `build.py --force` is now refused by the permission layer
as irreversible local destruction, closing off the remedy both drift gates point to.
