---
title: "pull-request agent — Reference"
type: reference
status: active
created: 2026-05-07
last_updated: 2026-05-07
components:
  - "infrastructure"
related_docs:
  - "docs/agents/conventions.md"
  - "docs/architecture/adrs/ADR-006-agent-model-tiers.md"
  - "tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md"
related_code:
  - ".claude/agents/pull-request.md"
  - ".agents/workflows/pull-request.md"
  - ".agents/workflows/commit-push-pr.md"
---

# pull-request agent

The `pull-request` agent is the PR-creation half of the commit -> push -> PR
shipping chain. It runs after the `commit` agent has committed the change,
drafts a PR title and body, asks the user for confirmation, then pushes the
branch and calls `gh pr create`. On merge conflicts it delegates to
`conflict-resolver` and retries once.

---

## When to use

- Type `/pull-request` to invoke directly on an already-committed branch.
- Type `/commit-push-pr` to run the full chain: commit then PR creation.
- The agent auto-triggers on prose such as "open a PR", "create a pull request",
  or "push and open a PR for this branch".

---

## Confirmation flow

The agent is **confirmation-gated**. It never runs `git push` or
`gh pr create` without an explicit user yes in the same turn.

1. It reads `git log origin/<base>..HEAD` and `git diff --stat` to understand
   the change.
2. It drafts a title (<=70 chars, imperative mood) and a body (Summary bullets
   + Test plan checklist + Generated-with footer).
3. It presents the draft as:

   ```
   Proposed PR:

     Title: <title>
     Body:  <body>
     Branch: <branch> -> <base>

   OK to push and open the PR? (yes / edit / cancel)
   ```

4. On "yes": push + `gh pr create`.
5. On "edit": re-draft with the user's corrections and re-present.
6. On "cancel" or anything negative: stop.

---

## Conflict flow

If the push is rejected due to a non-fast-forward or diverged history:

1. The agent runs `git fetch` and a dry-run merge to collect conflicted files.
2. It spawns `conflict-resolver` via the Agent tool, passing:
   - `conflicted_files` (list)
   - `branch` (current branch)
   - `base` (target base branch)
3. `conflict-resolver` returns an `escalation` field:
   - `escalation: none` -- resolved automatically. Agent retries the push.
   - `escalation: opus` -- Opus was used for resolution. The agent surfaces the
     `resolved_diff` to the user before retrying.
4. **One retry only.** If the retry also fails, the agent stops and reports the
   error. It does not loop.

---

## Refusal cases

| Trigger | Behaviour |
|---|---|
| "push --force to main" in the user's message | Refuse, cite the Git Safety Protocol, stop |
| Force-push to a non-main branch | Allowed if the user names the branch explicitly |
| User says "cancel" at the confirmation step | Stop immediately, no push |

---

## PR body template

The agent uses the project's standard template:

```
## Summary
- <bullet>

## Test plan
- [ ] <step>

Generated with [Claude Code](https://claude.com/claude-code)
```

This matches the template in the project base instructions (CLAUDE.md) for
`gh pr create`.

---

## Chain position

```
/commit-push-pr
  |
  +--> commit agent (ticket 09)   [depth 1]
  |       commits, fixes hooks
  |
  +--> pull-request agent (this)  [depth 1, or 2 from /commit-push-pr]
          |
          +--> conflict-resolver  [depth 2 / 3 from /commit-push-pr, on conflict only]
```

`conflict-resolver` is the deepest node; it does not spawn further agents
except when escalating to Opus (which is also a depth-bounded sub-agent call).

---

## Smoke-test recipe

**Purpose**: verify the full commit -> PR chain including conflict-resolver.

**Setup**:

1. Create a feature branch: `git checkout -b smoke/pr-conflict-test`
2. Modify a file that also has a pending change on `main` (to create a
   diverged history).
3. Commit the change on the feature branch.
4. Push `main`'s conflicting commit to origin without merging.

**Execution**: run `/commit-push-pr` from the feature branch.

**Expected**:

1. Commit agent completes (or is skipped if already committed).
2. pull-request agent drafts PR and asks for confirmation.
3. After confirming, push is rejected (non-fast-forward).
4. `conflict-resolver` fires; resolves (or escalates to Opus).
5. Retry push succeeds.
6. `gh pr create` returns a PR URL.

**Cleanup**: delete the test branch and close the PR.

---

## See also

- [Agent conventions](../conventions.md) -- frontmatter schema, visibility
  classes, tool allowlists, patterns.
- [ADR-006](../../architecture/ADR-006-agent-model-tiers.md) -- policy source
  for model tiers, gatekeeper escalation, confirmation-gated visibility class.
- [EPIC-CodingAgents Master_Plan](../../../tickets/09_done/EPIC-CodingAgents/Master_Plan.md)
- [Ticket 12](../../../tickets/09_done/EPIC-CodingAgents/12_pull_request_agent.md)
- [Ticket 11 -- conflict-resolver](../../../tickets/09_done/EPIC-CodingAgents/11_conflict_resolver_agent.md)
- [Ticket 09 -- commit agent](../../../tickets/09_done/EPIC-CodingAgents/09_commit_agent.md)
