---
description: >
  Orchestrates the hardened post-merge feature finalization sequence with
  a pre-merge test baseline, merge-first step, triage-driven halt gate,
  pre-merge ticket/AC closure (step 3.5 — commits status: done and
  source AC work_status: done on the feature branch before the PR merge),
  and auto-ticketing for pre-existing failures. Requires Claude Code >= 2.1.154
  (workflow script support). The legacy LLM agent fallback was removed — see
  ADR-006.
---

# finalize-feature workflow

## Step map

| Step | Name | Description | Halt categories |
|------|------|-------------|-----------------|
| 0 | `capture_baseline` | Create a temporary detached worktree at `origin/main`, run the full test suite, store the list of failing test IDs as the pre-merge baseline, then remove the temp worktree. Graceful on failure — if the baseline cannot be captured the workflow continues with `baseline_failures = null` and triage classifies all post-merge failures conservatively as regressions. | — |
| 1 | `open_pr` | Probe for an open PR on the current branch. If none exists, dispatch the `pull-request` agent to create one. | — |
| 2 | `merge_main_into_worktree` | Merge `origin/main` into the feature worktree using `--no-commit --no-ff`. On conflict, run `git merge --abort` and halt. On success the worktree reflects the post-merge tree for test runs. | `merge_conflict` |
| 3 | `post_merge_tests_and_triage` | Run the full test suite on the post-merge worktree. Collects `failing_tests` list. If no failures, skip triage sub-steps and continue. When failures exist, dispatch `test-failure-triage` with `post_merge_failures`, `baseline_failures`, `baseline_sha`, `feature_branch`, and `changed_files`. If `triage_report.blocks_finalization == true`: hard halt — step 4 (PR merge) is structurally unreachable. If `false`: continue (all failures are pre-existing). | `test_regression` |
| 3.5 | `pre_merge_ac_closure` | **Runs on the feature branch, before the PR merge.** First resets/aborts the Step 2 `--no-commit --no-ff` test-merge so the closure commit is clean (no premature origin/main content). Then finds in-scope tickets where `status != done`, sets `status: done` in each ticket's frontmatter, and for each ticket with a `source_ac` field invokes `mark_ac_done.py --ticket <path> --ac-root docs/acceptance-criteria/`. Any non-zero `mark_ac_done.py` exit is logged as a WARNING — AC closure is non-fatal and finalize proceeds. Commits all changes as a single `chore(tickets): close tickets and source ACs` commit on the feature branch so the PR merge carries closure to `origin/main` atomically. Idempotent: already-closed tickets and ACs are no-ops; skipped entirely when the closure commit already exists or the PR is already merged. Reports `tickets_closed`, `acs_closed`, `acs_skipped` in the return payload. | — |
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
- Triage agent: `templates/agents/test-failure-triage.md`

# v2.1.154+: deterministic JS workflow (leaf workflow — no nested workflow() calls)

> **Requires Claude Code >= 2.1.154.** If your install does not support the
> Workflow tool, you will see this error — do not proceed:
>
> ```
> Error: /finalize-feature requires Claude Code >= 2.1.154.
> The legacy LLM agent fallback was removed in EPIC-FinalizeFeatureHardening
> because the depth-1 sub-agent limit made it non-functional (ADR-006).
> Please upgrade Claude Code and re-run /finalize-feature.
> ```

Invoke `finalize-feature.js` with: $ARGUMENTS
