---
title: How to use /finalize-feature
description: Step-by-step guide for running /finalize-feature to merge a feature branch,
  run post-merge tests, and close tracking tickets.
last_updated: 2026-07-15
audience: developers
created: '2026-07-15'
type: tutorial
status: active
components:
  - finalize
---
# How to use /finalize-feature

`/finalize-feature` finalizes a feature branch end-to-end: it captures a
pre-merge test baseline, opens a PR if one is missing, merges `origin/main`
into the worktree, runs post-merge tests with triage, merges the PR to main
only when tests pass, auto-tickets any pre-existing failures, closes tracking
tickets, and removes the feature worktree.

Run it from the feature branch:

```
/finalize-feature
```

---

## What the workflow does

The workflow runs a deterministic sequence of steps. Each step probes observable
state before acting, so re-running after a crash or halt resumes from the first
incomplete step.

| Step | Name | What happens |
|------|------|--------------|
| 0 | Capture baseline | A temporary detached worktree is created at `origin/main`. The test suite runs there. The list of failing test IDs is stored as the **pre-merge baseline**. The temp worktree is then removed. If baseline capture fails for any reason, the workflow continues (graceful degradation) — a **targeted rerun** of only the post-merge failing test IDs is then attempted against `origin/main` HEAD to build a **recovered baseline** for triage. Only if that targeted rerun is also unavailable does triage fall back to conservative classification. |
| 1 | Open PR | If no open PR exists for the branch, the `pull-request` agent opens one. |
| 2 | Merge main into worktree | `origin/main` is merged into the feature worktree with `--no-commit --no-ff`. This gives step 3 a realistic view of the post-merge state. On conflict the merge is aborted and the workflow halts. |
| 3 | Post-merge tests + triage | The full test suite runs against the post-merge worktree. If all tests pass, the triage sub-steps are skipped and the workflow proceeds to step 4. When failures exist, the `test-failure-triage` agent classifies each failing test as `regression` (caused by this branch), `pre_existing` (already failing on main), or `flaky`. If `blocks_finalization == true` (regressions found), finalization halts here — **the PR is not merged**. If `false` (all failures are pre-existing), the workflow continues to step 4. |
| 4 | Merge PR | This step is only reached when `blocks_finalization === false`. You are prompted: `Merge PR #N (<branch> → main)?`. On `yes`, the PR is merged via `gh pr merge`. On `no`, finalization halts with no changes made to main. |
| 5 | Sync local main | `git checkout main && git pull`. The new HEAD SHA is reported. |
| 6 | Create tracking tickets + close | A `create-ticket` call is dispatched for each `pre_existing` or `flaky` triage entry, producing inbox tracking tickets. Then `status-checker` closes the branch's tracking tickets and archives the epic (if applicable). |
| 7 | Remove worktree | If the feature worktree still exists, `worktree-agent remove` is dispatched (with its own confirmation gate). |

---

## When finalization halts

### `merge_conflict` (step 2)

**What it means:** `git merge origin/main --no-commit --no-ff` produced
conflicts. The merge was automatically aborted — your worktree is clean.

**Diagnosis steps:**

1. Check which files conflict:
   ```bash
   git diff --name-only origin/main HEAD
   ```
2. Rebase or merge main into your branch manually:
   ```bash
   git fetch origin main
   git merge origin/main
   # resolve conflicts in your editor
   git add <resolved files>
   git merge --continue
   ```
3. Push the resolved branch, then re-run `/finalize-feature`.

---

### `test_regression` (step 3)

**What it means:** The triage agent found one or more failing tests classified
as **regressions** — tests that pass on `main` but fail on the post-merge
worktree, meaning this branch introduced a breakage. **The PR has not been
merged to main.**

**Null-baseline recovery (targeted rerun):** When the Step 0 full-suite baseline
timed out, the workflow performs a **targeted rerun** of only the post-merge
failing test IDs against a fresh `origin/main` checkout (after the same
`build.py` deploy step). This builds a **recovered baseline** and supplies it to
triage in place of `null`. Tests that also fail on `origin/main` are classified
`pre_existing` and do not block finalization. Only if this targeted rerun is also
unavailable (checkout or build fails) does triage fall back to the conservative
path — the halt message lists each failing test's `modified_by_branch` flag so
you can adjudicate which tests this branch actually touched.

The `triage_report` in the halted result shows:

- `regressions` — test IDs that are newly failing (must be fixed).
- `pre_existing` — test IDs already failing on main (do not block finalization).
- `flaky` — test IDs that are intermittently failing (do not block finalization,
  but tracking tickets will be created).
- `summary` — one-sentence triage summary.

Each triage entry also includes `modified_by_branch` — whether the test file was
modified by this branch — to help distinguish genuine regressions from pre-existing
failures the branch did not touch.

**What to do:**

1. Read the `triage_report.regressions` list.
2. Fix each regressed test on the feature branch.
3. Push the fix commits.
4. Re-run `/finalize-feature`. The workflow resumes from step 0 (captures a
   fresh baseline) and retests.

---

### `user_declined_merge` (step 4)

**What it means:** You answered `no` to the merge prompt.

**What to do:** No changes were made to main. Re-run `/finalize-feature` when
you are ready to merge.

---

### `worktree_conflict_pids` (step 7)

**What it means:** The `worktree-agent` reported processes holding locks on
the worktree path, preventing removal.

**What to do:**

1. Note the `conflict_pids` list in the halted result.
2. Check each PID:
   ```bash
   ps aux | grep <pid>
   ```
3. If the process is idle or belongs to a previous run:
   ```bash
   kill <pid>
   ```
4. Re-run `/finalize-feature`. The workflow resumes — steps 0–6 are
   already complete and will be skipped.

---

## Pre-existing failures and tracking tickets

When the triage agent finds `pre_existing` or `flaky` failures (failures
already present on `main`), the workflow automatically creates a tracking
ticket in `tickets/00_inbox/` for each one before continuing.

Each tracking ticket contains:

- The failing test ID.
- The `origin/main` SHA at which the failure was recorded.
- The triage category (`pre_existing` or `flaky`).
- The timestamp of the baseline run.

You can find the created tickets at:

```
tickets/00_inbox/TICKET-YYYYMMDD-<slug>.md
```

These tickets are not blocking — finalization continues after they are
created. They are for future investigation and should be prioritised through
the normal backlog process.

---

## Version notes

- **Claude Code >= 2.1.154**: uses `templates/workflows-js/finalize-feature.js`
  (deterministic JS workflow, full 8-step sequence). This is the only supported path.
- **Claude Code < 2.1.154**: the Workflow-tool required to run `finalize-feature.js`
  is not available. The legacy LLM agent fallback (`templates/agents/finalize-feature.md`)
  has been **removed** as of EPIC-FinalizeFeatureHardening. On older installs, invoking
  `/finalize-feature` will emit an explicit error:

  > "requires Claude Code >= 2.1.154; the legacy agent fallback was removed because
  > Claude Code's depth-1 Agent-tool limit made it non-functional — all sub-agent
  > dispatches were silently dropped. Please upgrade."

  **Action required**: upgrade Claude Code to >= 2.1.154 before using `/finalize-feature`.

---

## See also

- Workflow doc: `templates/workflows/finalize-feature.md`
- JS implementation: `templates/workflows-js/finalize-feature.js`
- Triage agent: `templates/agents/test-failure-triage.md`
