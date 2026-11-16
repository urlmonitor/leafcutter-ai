---
title: "KI-BO-20261101-shell-reply-schema-admits-a-wrapped-reply — shell-runner put its whole reply object, as a string, inside `stdout`; the shell-reply schema requires no field, so the reply passed it, and shellStepReply() halted the run with 'the reply carries no exit status'"
description: "low — on 2026-10-29 (run wf_51e76d5e-04e) /plan-feature's first step, read-workspace-marker, went to shell-runner with SHELL_REPLY_SCHEMA. The reply was {\"stdout\": \"{\\\"command\\\": ..., \\\"exit_status\\\": 0, \\\"stdout\\\": ..., \\\"stderr\\\": \\\"\\\"}\"}. SHELL_REPLY_SCHEMA (_shared/workspace-answer.js:7-18) lists properties but no `required`, so it does not force exit_status. shellStepReply() rejects at :87-88 with no retry. A fresh run three minutes later worked. Not an occurrence of KI-BO-20261101-plan-feature-script-steps-declined-by-worktree-agent: right agent, no decline, shape only."
type: reference
category: reference
status: active
created: '2026-11-01'
last_updated: '2026-11-01'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-low-ki-bo-20261101-plan-feature-script-steps-declined-by-worktree-agent.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260928-pause-verify-rejects-an-enveloped-read-back.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261023-fast-lane-step-reader-rejects-relay-noise.md
---

# KI-BO-20261101-shell-reply-schema-admits-a-wrapped-reply — shell-runner wrapped its whole reply inside `stdout`, the schema let it through, and the run halted with "the reply carries no exit status"

> Filed 2026-11-01. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. The halt is loud, happens before anything is written, and a rerun worked. But
  the message reads as a workspace problem when the workspace was fine. It happens on the first
  step of the run, so the run cannot start until the user retries.
- **Status:** open. No AC.
- **Occurrences:** 1 (`/plan-feature` run `wf_51e76d5e-04e`, step `read-workspace-marker`,
  workspace `ac/tq-200d-before-score-fixes`, 2026-10-29 19:52 UTC). A resume of the same run id
  replayed the cached reply and failed the same way (19:55). A fresh run (`wf_4a8567df-505`, 19:55)
  got a well-formed reply from the same step and agent.
- **First seen:** 2026-10-29 · **Last seen:** 2026-10-29
- **Where** (`templates/workflows-js/_shared/workspace-answer.js` at base `d62440669`; copied
  into each consuming workflow between the `WORKSPACE-ANSWER` markers at build time):
  - `:7-18` — `SHELL_REPLY_SCHEMA`: `type: "object"` and seven optional `properties`, no
    `required`.
  - `:133` — `shellStepDispatch()` sends every shell step to `shell-runner` with that schema.
  - `:176` — `resolveMakerFromMarker()` dispatches `cat <workspace>/.leafcutter/workspace.json` as
    `read-workspace-marker` and reads the reply with `shellStepReply()`.
  - `:86-88` — `shellStepReply()` takes `exit_status` or `exit_code`, and when neither is a number
    returns `"no valid answer was received from " + step + " (the reply carries no exit status)"`.

## Symptom

The run returned `status: "error"`:

> Workspace step failed: no valid answer was received from read-workspace-marker (the reply carries
> no exit status). Received: {"stdout":"{\"command\": \"cat \\\"C:\\\\Users\\\\...\\\\tq-200d-before-score-fixes/.leafcutter/workspace.json\\\"\", \"exit_status\": 0, \"stdout\": \"{\\n  \\\"schema_version\\\": 1, ...}\", \"stderr\": \"\"}"}. Nothing was dispatched after it and no other location was used.

The journal (`wf_51e76d5e-04e/journal.jsonl`, agent `ad2341637be39e54e`, `agentType:
"shell-runner"`) holds the same reply. The command ran, exited 0 and read the marker. The agent then
put its whole correct answer, serialised, into the `stdout` field of the structured reply.

## Mechanism

1. The step is routed correctly. `read-workspace-marker` goes to `shell-runner` (`:133`), the agent
   chartered to run one command and relay it (ADR-070), and it did run the command.
2. The schema does not fix the shape. `SHELL_REPLY_SCHEMA` (`:7-18`) has no `required` list, so
   `{"stdout": "<anything>"}` is a valid reply. Structured output stops prose, but it does not stop
   the agent nesting its answer one level down.
3. The reader looks at the top level only. `shellStepReply()` finds no numeric `exit_status` or
   `exit_code` (`:86-87`) and rejects at `:88`. It does not look inside a `stdout` string that is
   itself a reply object.
4. No retry. `resolveMakerFromMarker()` returns the rejection, and the run halts on its first step.
   A resume replays the cached reply, so only a fresh run gets a new answer.

## Why this is not an occurrence of KI-BO-20261101-plan-feature-script-steps-declined-by-worktree-agent

That issue is about routing: steps sent to `worktree-agent`, whose charter forbids them, which
declines in prose. Here the step went to the right agent, which did not decline and did run the
command; only the reply's shape was wrong, and the dispatch already carried a schema. The fixes
differ too: that one needs the steps moved to `shell-runner`, and this one is in the
`shell-runner` path the move would use. Both share the reader weakness (a reply that is not a
plain result fails without saying why or trying again), so a fix to `shellStepReply()` helps both.

The closest earlier entry is `KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back`: an agent
wrapped a correct answer one level down and a top-level-only check rejected it. There the dispatch
had no schema at all; here it had one and it was too loose. Filed separately because the site,
agent and reader differ.

## Detection

A `Workspace step failed: no valid answer was received from <step> (the reply carries no exit
status)` whose `Received:` text starts `{"stdout":"{\"command\":` and contains `\"exit_status\"`.

## Workaround

Start a fresh run (not a resume of the failed run id, which replays the cached reply). That worked
on 2026-10-29.

## Fix direction

1. Add `required: ["exit_status", "stdout", "stderr"]` to `SHELL_REPLY_SCHEMA`, with a decline
   reply allowed through `oneOf` (`declined`, `agent`, `reason`), so the schema itself refuses a
   reply that has no exit status.
2. In `shellStepReply()`, when the only field is a `stdout` string that parses to an object with a
   numeric `exit_status`, unwrap it once. Or re-ask once with the received reply quoted, as
   `readPauseRecordWithRetry()` does, before halting.
3. Add a test that feeds `shellStepReply()` this exact wrapped reply.

**Pattern:** a schema that names fields without requiring any. It reads as a contract but does not
fix the one field the reader needs.
