---
description: >
  Orchestrates the hardened post-merge feature finalization sequence with
  a pre-merge test baseline, merge-first step, triage-driven halt gate, and
  auto-ticketing for pre-existing failures. Primary path: the
  finalize-feature.js workflow script (Claude Code >= 2.1.154). Fallback
  path: the finalize-feature LLM agent (older versions, 6-step flow only).
---

# finalize-feature workflow

## Step map

| Step | Name | Description | Halt categories |
|------|------|-------------|-----------------|
| 0 | `capture_baseline` | Create a temporary detached worktree at `origin/main`, run the full test suite, store the list of failing test IDs as the pre-merge baseline, then remove the temp worktree. Graceful on failure — if the baseline cannot be captured the workflow continues with `baseline_failures = null` and triage classifies all post-merge failures conservatively as regressions. | — |
| 1 | `open_pr` | Probe for an open PR on the current branch. If none exists, dispatch the `pull-request` agent to create one. | — |
| 2 | `merge_main_into_worktree` | Merge `origin/main` into the feature worktree using `--no-commit --no-ff`. On conflict, run `git merge --abort` and halt. On success the worktree reflects the post-merge tree for test runs. | `merge_conflict` |
| 3 | `post_merge_tests_and_triage` | Run the full test suite on the post-merge worktree. Collects `failing_tests` list. If no failures, skip triage sub-steps and continue. When failures exist, dispatch `test-failure-triage` with `post_merge_failures`, `baseline_failures`, `baseline_sha`, `feature_branch`, and `changed_files`. If `triage_report.blocks_finalization == true`: hard halt — step 4 (PR merge) is structurally unreachable. If `false`: continue (all failures are pre-existing). | `test_regression` |
| 4 | `merge_pr` | Prompt gate: only reached when `blocks_finalization === false` (tests passed or all failures are pre-existing). Present branch name and PR number. On `yes` dispatch `pull-request` to merge via `gh pr merge`. A defensive guard returns `status: halted` with `reason: test_regression` if `blocks_finalization` is truthy at this point. | `user_declined_merge` |
| 5 | `sync_local_main` | `git checkout main` then `git pull`. Reports new HEAD SHA to the user. | — |
| 6 | `create_pre_existing_tickets_and_close` | For each `pre_existing` or `flaky` triage entry, dispatch `create-ticket` to produce an inbox tracking ticket. Non-fatal: failure to create a ticket logs a warning and continues. Then dispatch `status-checker` to detect branch scope and close tickets / archive the epic. Includes folder reconciliation (EPIC-MoveOnMainOnly/03). | — |
| 7 | `remove_worktree` | Probe `git worktree list`. If the feature worktree still exists, dispatch `worktree-agent remove` (confirmation gate delegated to the agent). | `worktree_conflict_pids` |

## Halt categories

| Category | Halted at | Meaning | Resolution |
|----------|-----------|---------|------------|
| `merge_conflict` | Step 2 | `git merge origin/main --no-commit --no-ff` returned a conflict. `git merge --abort` was run automatically. | Resolve conflicts on the feature branch, commit, push, then re-run `/finalize-feature`. |
| `test_regression` | Step 3 | `triage_report.blocks_finalization == true` — one or more failing tests are classified as regressions introduced by this branch. The PR has NOT been merged. | Fix the regressions on the feature branch (new commits), push, then re-run `/finalize-feature`. |
| `user_declined_merge` | Step 4 | User answered `no` to the merge prompt. No changes made to main. | Re-run `/finalize-feature` and answer `yes` when ready to merge. |
| `worktree_conflict_pids` | Step 7 | `worktree-agent` reported conflict PIDs blocking worktree removal. | Terminate or resolve the listed PIDs, then re-run `/finalize-feature`. |

## Cross-references

- How-to guide: `docs/how-to/finalize-feature.md`
- JS implementation: `templates/workflows-js/finalize-feature.js`
- Legacy agent (pre-2.1.154): `templates/agents/finalize-feature.md`
- Triage agent: `templates/agents/test-failure-triage.md`

# v2.1.154+: deterministic JS workflow (leaf workflow — no nested workflow() calls)
Invoke `finalize-feature.js` (Claude Code >= 2.1.154) or the `finalize-feature` agent (older versions) with: $ARGUMENTS
