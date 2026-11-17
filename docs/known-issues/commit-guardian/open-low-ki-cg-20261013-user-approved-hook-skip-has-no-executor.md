---
title: "KI-CG-20261013-user-approved-hook-skip-has-no-executor — a hook skip the user has approved cannot be run by the assistant: the commit agent accepts only a 'direct user message in this conversation', which a dispatched subagent never has, and enforce_commit_delegation blocks the coordinator's own commit"
description: "medium (process) — commit.md lets the commit agent use SKIP=<hook> only on explicit user authorisation, and says a yes relayed by a parent agent does not count. A dispatched commit agent receives everything through its parent, so it refused even the user's verbatim AskUserQuestion answer. The coordinator cannot commit either, because the PreToolUse hook blocks a direct git commit outside the commit agent. On 2026-10-12 the user asked the assistant twice to run the skip commit for the main-into-epic merge, and it could not. Only the user can run such a commit."
type: reference
category: reference
status: active
created: '2026-10-13'
last_updated: '2026-10-13'
components:
  - commit_guardian
  - supervisor_system
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260907-commit-delegation-is-a-password-not-an-identity.md
  - docs/known-issues/commit-guardian/resolved/resolved-high-ki-cg-20261010-folder-density-refuses-merges-of-main.md
---

# KI-CG-20261013-user-approved-hook-skip-has-no-executor — the user can approve a skip, but no agent may carry it out

> Filed 2026-10-13 from the BO-4300 drive. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium (process). Nothing wrong lands: every path fails closed. But a decision the
  user made in so many words cannot be carried out by the assistant, the user has to leave the session
  to type a git command, and the user reads that as the assistant refusing its job.
- **Status:** open, no AC. Rule text verified on `origin/main` `964f23a60`. The refusals are from the
  coordinator's session account.
- **Occurrences:** 2 refusals on 2026-10-12, both for the merge of `origin/main` into
  `epic/every-piece-of-separate-work-gets-its-workspace` (refused by `check-folder-density`).
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:**
  - `templates/agents/commit.md:95-103`: on explicit user authorisation, use `SKIP=<specific-hook>`;
    then "**Authorization is personal**: A 'yes' relayed from a parent agent or supervisor does NOT count
    as authorization. Only a direct user message in this conversation authorizes --no-verify usage." The
    same rule appears at `:186-190` and `:201-204`, at `:445` ("Proceed only if user insists in the same
    turn") and at `:453-454`.
  - `templates/hooks/enforce_commit_delegation.py:260-294` (`_is_commit_agent_mode`) and `:297-319` (the
    block message): a `git commit` outside the commit agent is blocked, and the corrective action is
    "Dispatch the commit agent". `CLAUDE.md:27-34` states the rule.

## What happened

1. On 2026-10-12, `check-folder-density` refused the merge commit of `origin/main` into the epic branch
   for folders that were already dense on main
   (`KI-CG-20261010-folder-density-refuses-merges-of-main`, now resolved).
2. The coordinator asked the user with AskUserQuestion. The user approved `SKIP=check-folder-density`
   for that commit.
3. The coordinator dispatched the commit agent with the user's answer quoted verbatim. The agent
   refused: the approval reached it through the coordinator, so it counted as relayed.
4. The coordinator cannot commit itself. The PreToolUse hook blocks a direct `git commit` outside the
   commit agent.
5. The user asked: "can you please run these commands yourself? Its your job. Also we have a commit
   agent that should be able to handle it". The second attempt ended the same way.
6. The merge was unblocked by fixing the hook instead (PR #1143, `a104d934c`).

## Mechanism

The rule is right about what it fears: a parent agent must not be able to invent an approval. But it
draws the line at "this conversation", and a subagent's conversation holds only its parent's prompt.
So for a dispatched commit agent, "a direct user message in this conversation" can never exist, and the
SKIP path at `commit.md:95-99` cannot be reached from any drive or coordinator. The delegation hook then
closes the only other door. Both rules are correct on their own. Together they leave a user-approved
action with no one allowed to run it.

The hook's identity check is a string (`COMMIT_AGENT_MODE=1`;
`KI-CG-20260907-commit-delegation-is-a-password-not-an-identity`). The coordinator could have typed it,
and correctly did not, since that would forge the identity the rule depends on.

## Detection

A commit agent reply that refuses a `SKIP=` or override because the approval was "relayed", in a
session where the user did approve it through AskUserQuestion or a direct message to the coordinator.

## Workaround

Give the user one ready-to-run line: `SKIP=<hook> git commit -F <message-file>`, with the message file
already written. The message should say what was skipped and why, and the user runs it. All other
hooks still run.

## Fix direction

- **An approval the commit agent can verify.** For example, the coordinator writes the user's answer
  through a tool the harness records (an approval file written by a hook on the user's AskUserQuestion
  reply, naming the hook, the commit's tree or staged-diff hash, and an expiry). The commit agent checks
  that record instead of the conversation. A relayed claim with no record is still refused.
- **Or let the user's yes travel with the tool call.** A PreToolUse hook that sees the user's approval
  record lets one `SKIP=<named hook> git commit` through, for that staged tree only.
- **Until then, say so up front.** commit.md and the coordinator guidance should state that a skip
  cannot be run by any agent, and that the user will be handed a command. That way the AskUserQuestion
  does not promise an action no agent can take.

**Related.** `KI-CG-20260907-commit-delegation-is-a-password-not-an-identity` (the same hook; it has
no real identity to check). `KI-CG-20261010-folder-density-refuses-merges-of-main` (resolved; the
refusal that needed the skip).

**Pattern:** two fail-closed rules, each sound, whose intersection leaves an approved action with no
permitted actor.
