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
| 2 | `merge_pr` | Prompt gate: present branch name, PR number, and commit count. On `yes` dispatch `pull-request` to merge via `gh pr merge`. | `user_declined_merge` |
| 3 | `sync_local_main` | `git checkout main && git pull`. Reports new HEAD SHA to the user. | — |
| 3.5 | `merge_main_into_worktree` | Merge `origin/main` into the feature worktree using `--no-commit --no-ff`. On conflict, run `git merge --abort` and halt. On success the worktree reflects the post-merge tree for test runs. | `merge_conflict` |
| 4a | `post_merge_test_run` | Run the full test suite on the post-merge worktree. Collects `failing_tests` list. If no failures, skip 4b and 4c. | — |
| 4b | `triage_failures` | Dispatch `test-failure-triage` with `post_merge_failures`, `baseline_failures`, `baseline_sha`, `feature_branch`, and `changed_files`. Returns a `triage_report` that classifies each failure as `regression`, `pre_existing`, or `flaky`, and sets `blocks_finalization`. | — |
| 4c | `halt_or_continue` | If `triage_report.blocks_finalization == true`: hard halt — steps 5 and 6 are structurally unreachable. If `false`: continue (all failures are pre-existing). | `regressions_or_stale_tests` |
| 5 | `create_pre_existing_tickets` | For each `pre_existing` or `flaky` triage entry, dispatch `create-ticket` to produce an inbox tracking ticket. Non-fatal: failure to create a ticket logs a warning and continues. Then dispatch `status-checker` to detect branch scope and close tickets / archive the epic. | — |
| 6 | `remove_worktree` | Probe `git worktree list`. If the feature worktree still exists, dispatch `worktree-agent remove` (confirmation gate delegated to the agent). | `worktree_conflict_pids` |

## Halt categories

| Category | Halted at | Meaning | Resolution |
|----------|-----------|---------|------------|
| `user_declined_merge` | Step 2 | User answered `no` to the merge prompt. No changes made. | Re-run `/finalize-feature` and answer `yes` when ready to merge. |
| `merge_conflict` | Step 3.5 | `git merge origin/main --no-commit --no-ff` returned a conflict. `git merge --abort` was run automatically. | Resolve conflicts on the feature branch, commit, push, then re-run `/finalize-feature`. |
| `regressions_or_stale_tests` | Step 4c | `triage_report.blocks_finalization == true` — one or more failing tests are classified as regressions introduced by this branch. | Fix the regressions on the feature branch (new commits), push, then re-run `/finalize-feature`. |
| `worktree_conflict_pids` | Step 6 | `worktree-agent` reported conflict PIDs blocking worktree removal. | Terminate or resolve the listed PIDs, then re-run `/finalize-feature`. |

## Cross-references

- How-to guide: `docs/how-to/finalize-feature.md`
- JS implementation: `templates/workflows-js/finalize-feature.js`
- Legacy agent (pre-2.1.154): `templates/agents/finalize-feature.md`
- Triage agent: `templates/agents/test-failure-triage.md`

# v2.1.154+: deterministic JS workflow (leaf workflow — no nested workflow() calls)
Invoke `finalize-feature.js` (Claude Code >= 2.1.154) or the `finalize-feature` agent (older versions) with: $ARGUMENTS
