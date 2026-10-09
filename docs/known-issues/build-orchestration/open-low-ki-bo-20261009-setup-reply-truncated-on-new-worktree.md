---
title: "KI-BO-20261009-setup-reply-truncated-on-new-worktree — on a first /plan-feature run the setup agent relays the bootstrap's whole stderr, truncates its own reply before the JSON line, and the run halts saying the setup named no workspace"
description: "medium — creating a new authoring worktree prints tens of thousands of characters of bootstrap output on stderr. The setup prompt asks the Haiku worktree agent to return stderr in its reply, the agent cut the reply short with a note that the full response was saved to a file, and the JSON line never arrived. Run wf_bfcfe2c8-006 halted as no workspace named despite the stdout and last-line fixes. A re-run on the existing worktree succeeds. Ticketed in the plan-feature setup-reply ticket filed 2026-10-08."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260928-pause-verify-rejects-an-enveloped-read-back.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260901-1620.md
---

# KI-BO-20261009-setup-reply-truncated-on-new-worktree — on a first /plan-feature run the setup agent relays the bootstrap's whole stderr, truncates its own reply before the JSON line, and the run halts saying the setup named no workspace

- **Severity:** medium. The run halts loudly, before any authoring agent, so nothing wrong is
  committed, and a re-run succeeds. But the halt reason is false: the workspace was created and
  its JSON was printed. It also hits the path a new project takes first, a first `/plan-feature`
  run per component, which is where the current roadmap outcome (self-onboarding, reliable
  across repos) needs it to work.
- **Status:** open. Ticket: `TICKET-20261008-PlanFeatureSetupReplyCarriesOnlyThePayload`
  (`tickets/00_inbox/`, PR #1065). Related done ACs: BO-1500a-1-ii (the setup command's stdout
  holds only the JSON), BO-1500a-5-i (an uninterpretable reply halts), BO-1500a-5-iii (parse the
  reply's last non-empty line). Each was right for the reply it saw; none bounds the reply's size.
- **Occurrences:** 1 (2026-10-07, run `wf_bfcfe2c8-006`). Session observation. Expected on every
  run that creates a new authoring worktree with similar bootstrap output, but only one run is
  recorded.
- **First seen:** 2026-10-07 · **Last seen:** 2026-10-07
- **Where:** `templates/workflows-js/plan-feature.js`, line numbers verified on origin/main
  `c79d41e34` (identical on this branch): the setup command, built with no redirection
  (:2484-2487); the dispatch prompt that asks for stderr in the reply (:2491-2496, the stderr
  field at :2494); the halt that names the failure (:2564). The setup agent is `worktree-agent`
  (:2366), pinned to Haiku (`templates/agents/worktree-agent.md:19`).

## Symptom

On a first run, `create-ac-worktree` creates a new authoring worktree. Its bootstrap prints tens
of thousands of characters: git checkout progress, the pip install and the build output. Since
BO-1500a-1-ii all of that goes to stderr, and stdout holds only the JSON payload. The setup agent
still reported both streams. It then cut its reply short with "... (FULL JSON RESPONSE SAVED TO
FILE)" before the JSON line. BO-1500a-5-iii's last-line parse therefore found no payload, and the
run halted with the setup failure kind `no_workspace_named` and the message "The isolated-workspace
setup step reported success but named no workspace directory."

A re-run with the worktree already in place succeeds, because the reuse path prints little.

## Mechanism

1. The prompt requires stderr in the reply: `Return JSON: { "output": "<raw stdout line>",
   "exit_code": <number>, "stderr": "<stderr or empty>" }` (:2494). The reply's size therefore
   grows with the bootstrap's output, and nothing bounds it.
2. A relaying model given tens of thousands of characters to echo truncates or summarises. Here it
   truncated, and the cut fell before the one line the workflow parses.
3. The parse fixes work on what arrives. Moving the bootstrap's output to stderr (BO-1500a-1-ii)
   and reading the last line (BO-1500a-5-iii) both assume the stdout line reaches the reply. When
   the reply is cut, there is no last line to read.

This is the same class as `KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back`: the
workflow's parse is exact, but the reply is shaped by an agent whose own output habits decide what
arrives. There the agent wrapped the payload. Here it truncated it.

## Detection

A `no_workspace_named` setup halt on a run that created a new worktree: `git worktree list` shows
the authoring worktree present, with a creation time matching the run. Or a reply in the run's
journal that ends with a "saved to file" note or another truncation marker instead of a JSON line.

## Workaround

Re-run `/plan-feature`. The worktree from the failed run is reused, setup prints little, and the
reply carries the JSON line.

## Fix direction

The ticket's: redirect the setup script's stderr to a log file whose path holds the run id, in a
git-ignored runtime folder, and drop stderr from the reply contract, so the reply is the exit code
and the one JSON line. On a non-zero exit, read the log's last lines back through a separate,
bounded dispatch so the failure stays diagnosable. The ticket's design note keeps a payload-file
alternative (`--payload-file`) for the case where the redirection cannot be made portable. Either
way, never ask an agent to relay output whose size the workflow does not control.

The durable remedy named in `KI-BO-20260901-1620` item 4, a chartered shell executor with no
output contract of its own, now exists as `command-step-runner` (BO-2400a-1-i). Routing this
dispatch to it does not close this entry alone: it hands back the command's output untouched, so
it would still be relaying the full bootstrap output.

**Pattern:** a reply contract that includes an unbounded stream, relayed by a model, parsed by an
exact reader.
