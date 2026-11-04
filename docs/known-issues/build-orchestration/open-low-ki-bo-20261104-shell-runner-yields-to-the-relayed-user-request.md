---
title: "KI-BO-20261104-shell-runner-yields-to-the-relayed-user-request — shell-runner declined plan-feature's one-command branch probe because the session's relayed request described a larger job, and the workflow halted on a probe its own skill calls best-effort"
description: "medium — the Workflow harness relays the session user's last message to every workflow agent and says it wins where the computed task conflicts. On run wf_29b7efbb-aca shell-runner read the user's multi-step ask (look at two KIs, plan-feature them, build the ACs) as conflicting with `git -C <root> branch --show-current` and declined. detectCurrentBranch() (plan-feature.js:2181-2189) turns any unusable reply into status error, although the plan-feature skill's §MP.4 says the probe is best-effort and skipped on failure. Nothing was written; a fresh run passed the same step."
type: reference
category: reference
status: active
created: '2026-11-04'
last_updated: '2026-11-04'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/architecture/adrs/ADR-070-shell-runner-runs-workflow-shell-commands.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261101-plan-feature-script-steps-declined-by-worktree-agent.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261101-shell-reply-schema-admits-a-wrapped-reply.md
---

# KI-BO-20261104-shell-runner-yields-to-the-relayed-user-request — shell-runner declined plan-feature's one-command branch probe because the session's relayed request described a larger job

> Filed 2026-11-04. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The run stopped at Stage 0 before any authoring and wrote nothing, and a
  fresh run passed the same step. But the stop is avoidable twice over: the agent declined a
  command its charter exists to run, and the workflow halted on a probe its own skill says is
  best-effort.
- **Status:** open. No AC.
- **Occurrences:** 1 (`/plan-feature` run `wf_29b7efbb-aca`, run id `pf-entry-pause-20261104`,
  workspace `ac/plan-feature-entry-and-pause-fixes`, 2026-11-04)
- **First seen:** 2026-11-04 · **Last seen:** 2026-11-04
- **Where:**
  - `templates/agents/shell-runner.md:53-59`: the "Decline Anything Else" pattern ("the request
    is not exactly one command line to run"). The charter does not say how to read a relayed
    user request.
  - `templates/workflows-js/plan-feature.js:2181-2189` — `detectCurrentBranch()`: `:2185`
    returns `status: "error"` for any reply `shellStepReply()` cannot use, a decline included.
  - `templates/skills/plan-feature/SKILL.md` §MP.4: "Branch detection is best-effort ... the
    detection is skipped silently and the workflow continues".

## Symptom

The workflow returned:

> Could not detect the current branch: the agent declined detect-current-branch (The relayed
> user request asks me to look at two known plan-feature issues, run plan-feature, and then run
> build-feature on the ACs. That is a multi-step workflow, not a request to run one command
> line, and this agent cannot plan or build features. The computed task asks for one git
> command, but the relayed request takes precedence where they conflict, so I ran nothing.).
> ... Nothing was dispatched after it.

## What the transcript shows

The Workflow harness (Claude Code, not this repository) sends every workflow agent two turns:

1. `[Workflow harness — user request]`: the session user's last message, verbatim, with "This
   relayed request is the only user voice in this task ... Where the computed task conflicts
   with this request, this request wins".
2. `[Workflow harness — computed task]`: here, "Run exactly this one command, once, unchanged
   ... `git -C "C:/Users/Hendrik/Code/leafcutter/leafcutter-ai" branch --show-current`".

The user's message was the request that started the whole session's work: look at two known
issues, run /plan-feature on them, then build the ACs. The branch probe is one step of that
/plan-feature run, so the two do not conflict. shell-runner (model `haiku`) read them as
conflicting and declined.

In the same run, `read-workspace-marker` went to the same agent type with the same relayed
request and ran. The next run (`wf_59d7a401-0f3`, identical args) ran `detect-current-branch`.
So the decline depends on how the model happens to read the relayed request; the command
and the charter were the same both times.

## Mechanism

1. **The charter gives the relayed request no frame.** shell-runner declines "anything else"
   than one command line. A relayed request that describes a multi-step job looks like
   "anything else" unless the charter says the relayed text describes the work the run
   serves, not the step in hand.
2. **A best-effort probe is fail-closed in code.** `detectCurrentBranch()` exists only for an
   informational log line when the checkout is on `main` (`:2186-2187`). §MP.4 says a failed
   detection is skipped. `:2185` instead ends the run for any unusable reply.

## Detection

A `status: "error"` starting "Could not detect the current branch: the agent declined". Open the
run's `journal.jsonl`; a decline whose `reason` cites "the relayed user request" is this
issue.

## Workaround

Start a fresh run with the same arguments (not a resume: a resume replays the cached decline).

## Fix direction

1. Give shell-runner's charter one rule for the relayed request: it describes the work the
   workflow run serves. A computed one-command task does not conflict with it unless the relayed
   request forbids that command or its effect. Decline only on the charter's own grounds.
2. Make `detectCurrentBranch()` match §MP.4: on any unusable reply, log the reason and continue.
   It decides nothing.
3. Check the other informational shell steps for the same fail-closed shape.

**Pattern:** an executor told that the user's words win, given no way to tell "the user's
words describe the bigger job" from "the user's words forbid this step".
