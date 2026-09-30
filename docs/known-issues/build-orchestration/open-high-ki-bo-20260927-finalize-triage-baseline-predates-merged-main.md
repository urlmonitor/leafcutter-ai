---
title: "KI-BO-20260927-finalize-triage-baseline-predates-merged-main — finalize-feature compares post-merge failures against a baseline taken at an older main, never reruns to confirm, and ignores collection errors, so failures that are not the branch's block the merge as regressions"
description: "high — Step 0 captures the baseline from the local origin/main ref before Step 2 fetches a newer one; the targeted rerun runs only when the baseline is null; the baseline parser keeps only FAILED lines. Observed 2026-09-25: 11 'new failures', 9 of them passed on rerun."
type: reference
category: reference
status: active
created: '2026-09-27'
last_updated: '2026-09-27'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260907-resume-replays-cached-resolver.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20260927-full-pytest-run-has-114-collection-errors.md
---

# KI-BO-20260927-finalize-triage-baseline-predates-merged-main — finalize-feature compares post-merge failures against a baseline taken at an older main, never reruns to confirm, and ignores collection errors, so failures that are not the branch's block the merge as regressions

- **Severity:** high. The merge gate reports "regression" for failures the branch did not cause, which is silent wrong behaviour at the step that decides whether code reaches main. The only way past it is to rerun by hand or to override the gate.
- **Status:** open — no AC. The mechanism is traced to code. The Windows-only failures in the evidence were real test bugs and have been fixed on `feature/windows-portable-tests`.
- **Occurrences:** 1 (2026-09-25, `/finalize-feature` of `feature/doc-index-posix-link-paths`, PR #892)
- **First seen:** 2026-09-25 · **Last seen:** 2026-09-25
- **Where:** `templates/workflows-js/finalize-feature.js` — Step 0 baseline `:782-833` (label `step-0-baseline`); Step 2 fetch and merge `:993-1020`; Step 3 test run `:1121-1133`; deploy-parity recheck `:1181-1245`; null-baseline targeted rerun `:1293-1388`; triage and halt `:1390-1470`.

## Symptom

Step 3 halted with `blocks_finalization: true` and 11 "new failures" against baseline `d2fe85a1`. By then main had moved to `ccea04ae`, and later to `cd8d4f69`. Of the 11:

- 9 (`unit_tests/build_orchestration/test_bo2400a_*`) passed when rerun by hand. They were intermittent, or they depended on state that had changed.
- 2, plus 3 doc-length tests, were Windows-only test bugs. They are fixed on this branch, but they were not regressions from the PR under finalization.

## Mechanism

1. **The baseline is taken at an older main than the one merged.** Step 0 runs `git worktree add --detach <tmp> origin/main` (`:795`) against the local `origin/main` ref, with no fetch. Step 2 then runs `git fetch origin main` (`:1003-1004`) and merges whatever arrived. Everything that landed on main between the last fetch and Step 2 is in the post-merge tree but not in the baseline. Under a resume, Step 0's result is also replayed from cache (see `KI-BO-20260907-resume-replays-cached-resolver`), so the baseline SHA stays fixed while main keeps moving. That is likely why `d2fe85a1` survived across the 2026-09-25 resumes (inferred, not reproduced).
2. **No rerun unless the baseline is missing.** The targeted rerun against `origin/main` (`:1293`) runs only when `baselineFailures === null`. When a baseline exists but is stale, the set difference goes straight to `test-failure-triage`. The triage prompt offers a `flaky` category (`:1393`), but gets no rerun data to base it on. The deploy-parity recheck (`:1181`) reruns failures only when a deployed artifact is missing, so it does not catch intermittent failures.
3. **Collection errors are invisible to the baseline.** Step 0 keeps only lines matching `'<file>::<test_name> FAILED'` (`:811`). A bare `pytest --tb=no -q` in this repo reports 114 collection `ERROR`s (see `KI-TQ-20260927-full-pytest-run-has-114-collection-errors`). Those tests never run on either side, and nothing records that they were skipped.
4. **Platform-only failures are not told apart.** The triage input carries no platform or environment signal, so a Windows-only test bug that entered main after the baseline (mechanism 1) reads the same as a regression. Why the five Windows-only failures in this run were missing from the baseline was observed, not yet traced: mechanism 1 is the likely cause, but it was not confirmed per test.

## Fix direction

- Take the baseline at the SHA that Step 2 will merge. Fetch before Step 0, or re-baseline in Step 3 when `origin/main` moved after Step 0 (compare `baseline_sha` with `git rev-parse origin/main`).
- Always rerun the candidate regressions, once on the merged tree and once at the merged main SHA, before triage. Classify a failure as a regression only if it fails on the branch and passes on main in the same run. That extends the existing null-baseline targeted rerun to every run.
- Parse `ERROR` lines as well as `FAILED` lines on both sides. Report collection errors as their own category.
- Make Step 0 depend on the current `origin/main` SHA, so a resume does not replay a stale baseline.

**Pattern:** a set difference taken between two snapshots of different bases, so everything that changed between the bases is blamed on the branch.
