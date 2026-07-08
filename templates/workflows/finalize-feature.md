---
description: |
  Step-map documentation for the finalize-feature.js workflow script.
  Covers pre-flight target resolution, step-by-step orchestration, and
  known edge-cases. This is a reference doc — the authoritative source
  of truth is the JS file itself.
---

# finalize-feature — Step Map

Reference for `templates/workflows-js/finalize-feature.js`.  
The workflow drives the post-merge feature finalization sequence as a flat
depth-1 agent chain (ADR-006).

## Pre-flight — Branch and Worktree Resolution

Resolves `branch` and `worktree_root` for all downstream steps.

**Anchors on the epic/ticket argument, not the session CWD
(TICKET-20260707-Finalize_Preflight_Branch_Detection, PR #231):** when the
caller passes a target argument (e.g. `/finalize-feature EPIC-FooBar`), the
pre-flight runs `git worktree list --porcelain` and matches the worktree whose
branch equals the argument, equals `feature/<argument>`, or contains it as a
substring (excluding `main`/`master`; shortest match wins on ties). Branch and
toplevel detection are then anchored with `git -C <worktree_root>`. This lets
`/finalize-feature` be invoked from anywhere — including the main repo checked
out on `main` — without a false "must be run from a feature branch" abort.

- If a matching worktree is found: `BRANCH` and `WORKTREE_ROOT` are set to that
  worktree's branch and absolute path.
- If no matching worktree is found: the workflow returns a clear, actionable
  error (`No worktree found matching '<argument>'`) rather than silently
  resolving to the wrong repo.
- If no argument is provided: falls back to CWD-based detection
  (`git branch --show-current` + `git rev-parse --show-toplevel`) for
  backward compatibility.

The "must be run from a feature branch" abort fires on the **resolved** branch,
never on the ambient CWD branch.

## Pre-flight 2 — GitHub Account Verification (EMU-aware)

Reads `gh_target_account` from the worktree's `settings.json`. If set,
verifies the active `gh` account matches and switches if needed. No-op when
`gh_target_account` is absent.

## Step 0 — Pre-merge Baseline Test Run

Creates a temporary detached worktree at `origin/main`, captures baseline
failing tests, then removes the worktree.

**Deploys shims before pytest (FIN-100a-4):** runs `scripts/build.py
--target-dir <temp-worktree>` before the test suite. This ensures
`commit_guardian`, `feedback` scripts, and `.pre-commit-config.yaml` are
deployed in the baseline environment — matching the production build state
so deploy-dependent tests are not spuriously red in the baseline.

Graceful degradation: if the worktree creation or build/test run fails,
`baselineFailures` is set to `null` and triage classifies all Step 3
failures as regressions (conservative).

## Step 1 — Open PR If Missing

Probes `gh pr list --head <BRANCH>`. If no PR exists, dispatches the
`pull-request` agent to open one. Includes EMU REST fallback when
`gh_repo` is configured.

## Step 2 — Merge origin/main Into Feature Worktree

Runs `git merge origin/main --no-commit --no-ff` inside the feature worktree
so Step 3 tests against the post-merge tree. On conflict: aborts the merge
and halts with `reason: merge_conflict`.

## Step 3 — Post-merge Tests + Triage

**Deploys shims before pytest (FIN-100a-4):** runs `scripts/build.py
--target-dir <WORKTREE_ROOT>` before the test suite. This is the same
build step as Step 0, ensuring identical deploy state so that deploy-dependent
tests cannot fail in one run and pass in the other.

Then runs the full test suite via pytest. If tests pass, skips triage and
proceeds to Step 4.

If tests fail, dispatches `test-failure-triage` to classify failures as
`regression | stale_test | pre_existing | flaky`. Halts with
`reason: test_regression` when `blocks_finalization === true`.

## Step 3.5 — Pre-merge AC Closure

Resets the Step 2 test-merge, finds open tickets introduced by the branch,
sets `status: done`, closes source ACs via `mark_ac_done.py`, and commits
on the feature branch — before the PR merges (so the closure commit lands
on `main` atomically with the feature).

## Step 4 — Merge PR to Main (Confirmation-Gated)

Probes PR state; skips if already merged. Presents a confirmation gate to
the user, then dispatches the `pull-request` agent to merge.

## Step 5 — Sync Local Main

Runs `git checkout main && git pull` anchored to `WORKTREE_ROOT`.

## Step 6 — Report Pre-existing / Flaky Failures + Scope Detection

Sub-step 6a: logs any pre-existing/flaky triage entries as untracked failures
(auto-ticketing is disabled — `create-ticket` is a workflow, not an agent).
Sub-step 6b: scope detection only (reads ticket frontmatter `status:`, no
writes on `main`).

## Step 7 — Remove Feature Worktree

Probes `git worktree list --porcelain`; delegates removal (with its own
confirmation gate) to the `worktree-agent`.

## Args Reference

| Arg | Type | Description |
|-----|------|-------------|
| `args` (positional string) | `string \| null` | Epic/ticket name to finalize (e.g. `EPIC-FooBar`). When provided, pre-flight resolves branch/worktree_root via `git worktree list --porcelain` (matching the argument against worktree branches) instead of the ambient CWD. |
| `baseline_ts` | `string \| null` | Timestamp suffix for the temp baseline worktree path. Replaces `Date.now()` (banned in E2). Defaults to `'baseline'` when absent. |
