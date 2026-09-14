---
title: "How to resume a paused /plan-feature run"
description: "Task-oriented guide for a run that stopped and reported itself waiting for an answer: list the runs that are waiting, see which of the five decision points each one is stopped at, and give the invocation that starts the route again with your answer -- covering all three ways that invocation ends."
type: how-to
category: how-to
status: active
created: 2026-09-14
last_updated: 2026-09-14
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
  - docs/architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md
  - docs/architecture/components/interactive-pause-resume-substrate.md
  - docs/how-to/approval-gate.md
---

# How to resume a paused /plan-feature run

This is about a `/plan-feature` run that **stopped and reported itself waiting**
for an answer at one of its five decision points, and how to give it that
answer so it continues. **This is not the readiness/approval gate** covered by
[How to use the readiness and approval gate](approval-gate.md) -- that page is
about the goal-to-epic ticket-generation gate and its `yes` / `review-all` /
`cancel` choices, which is not resumable and is none of the five decision
points a paused run is stopped at. That page's guide also declares
`components: [ac_driven_dev, build_orchestration]`, so it lands in the same
component view as this one; the two gates are unrelated and neither replaces
the other.

The five decision points a run can be waiting at, and what stops it there, are
depicted in
[Plan-Feature Decision Gates](../architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md).
This page does not repeat that -- it is the procedure for what you do once you
have found a run in that state.

## 1. Listing the runs that are waiting

A paused run's record lives on disk at
`<repo_root>/.leafcutter/paused_runs/<run_id>.json`, one file per waiting run,
under the filesystem the run's own writer resolved -- **not** the directory
the run happened to be started in (`ACD-2100a-4`: the store's location is a
function of the project, never of the caller's working directory, so this
works identically from the project root and from a worktree). Resolve the
same location a resumed run will look in and list it:

```bash
REPO_ROOT="$(dirname "$(git rev-parse --git-common-dir)")"
ls "$REPO_ROOT/.leafcutter/paused_runs/"
```

`git rev-parse --git-common-dir` -- not `--show-toplevel` -- is what makes
this resolve to the same directory whether you run it from the project's main
checkout or from a linked worktree of it; `--show-toplevel` would report the
worktree's own directory instead (`ACD-2100a-4`). Each filename, with the
`.json` suffix removed, is a waiting run's `run_id`.

## 2. Seeing which decision each one is waiting on

There is no `list` subcommand -- read each run's own record instead. Using the
same `$REPO_ROOT` from step 1:

```bash
python "$REPO_ROOT/.leafcutter/scripts/pause_store.py" \
  --store-dir "$REPO_ROOT/.leafcutter/paused_runs" \
  read --run-id <run_id>
```

This prints exactly one JSON object:

```json
{"exists": <bool>, "stale": <bool>, "record": <dict|null>}
```

When `exists` is `true`, `record.gate_id` names the decision that run is
waiting on (`ACD-2100c-2`: the durable record names the run and the decision
point it stopped at; `ACD-2100a-4`: the read resolves through the same
project-anchored store as the write, so a run written from a worktree is
still found here). Passing an explicit `--store-dir` matters even once the
script itself is found: `pause_store.py`'s own default falls back to
`git rev-parse --show-toplevel`, which is wrong from inside a worktree for
the same reason noted in step 1.

## 3. The invocation that resumes it with your answer

Do not edit the JSON file in `.leafcutter/paused_runs/` by hand -- the route
does not read a hand-edited record as an answer, and this only risks
corrupting the file the route itself is still waiting to be given a real
answer through. The invocation the route accepts is a re-run of the same
workflow with `resumeFromRunId` set to the run's `run_id` and the person's
decision supplied as `args.resume_answer` (ADR-024: "RESUME = re-invoke the
same workflow with the human's answer available and `resumeFromRunId` set, so
the harness replays committed `agent()` calls, execution deterministically
reaches the same gate, and the gate now finds the answer and proceeds").
`resume_answer` is this object:

```json
{
  "gate_id": "<the gate_id from step 2>",
  "type": "single_choice",
  "action": "approve",
  "channel": "person"
}
```

- `gate_id` -- must be the exact value read in step 2. `ACD-2100c-1` /
  `ACD-2100c-3` route this through the same subject-binding check the route
  uses to decide whether the answer applies at all.
- `type` -- the gate's own question type (`single_choice`, `priority_choice`,
  or `free_text`), read from `question.type` in the paused payload.
- `action` (or `choice`) -- the decision itself: `approve` / `edit` /
  `cancel` / `defer`, or the free-text/priority payload the question asked
  for.
- `channel` -- set to exactly `"person"` **only** when `action` is the
  decision you, the person running the route, actually made. `ACD-2100c-4`:
  anything else -- a different value, or leaving it out -- is refused as not
  attributable to the person, on purpose, regardless of how well-formed the
  rest of the answer is.

Tell the assistant running `/plan-feature` which paused run you are answering
(the `run_id` from step 1) and your decision; the `plan-feature` skill
constructs this re-invocation for you. This is the same `args.resume_answer`
contract [ADR-024](../architecture/adrs/ADR-024-interactive-pause-resume.md)
and the sequence in
[Plan-Feature Decision Gates](../architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md)
document from the route's own side.

## 4. What you observe

### The decision it was waiting on is applied, and the run continues

`ACD-2100c-3`: the run picks up from the decision point it was waiting on --
the steps before it do not run again, and the drafted work that was on disk
when it paused is carried forward unchanged. Once the run has moved past that
decision point, no record of it waiting remains: repeating step 2's read
against the same `run_id` now returns

```json
{"exists": false, "stale": false, "record": null}
```

and the run no longer appears in step 1's listing.

### Nothing to resume

`ACD-2100c-3`: if no waiting record exists for the `run_id` you supplied --
already answered, or never actually paused -- the run reports this rather
than starting a fresh run under the old run's identity:

```json
{"status": "nothing_to_resume", "run_id": "<run_id>", "gate_id": "<gate_id>"}
```

Nothing was drafted or discarded by this attempt: there was no waiting record
before it and there is none after it.

### The answer names a different decision than the one being waited on

`ACD-2100c-3-i`: if `resume_answer.gate_id` names a decision other than the
one the run is actually stopped at, that answer is not applied. The run stays
paused, reporting the decision it is genuinely waiting on:

```json
{"status": "paused_awaiting_input", "run_id": "<run_id>", "gate_id": "<gate_id>", "question": { ... }}
```

`gate_id` here is the run's real waiting point, not the one your answer named.
The drafted work is unchanged and nothing is discarded -- including when the
supplied answer names a choice that would have discarded work on the decision
it actually named. The waiting record on disk is untouched and still there:
repeat step 2's read with the `gate_id` this payload names, and supply a
`resume_answer` for that decision instead.

## See Also

- [Plan-Feature Decision Gates — Sequence Diagram](../architecture/diagrams/c3-008-plan-feature-decision-gate-sequence.md)
  -- all five decision points a run can be waiting at, and the three exits
  every one of them has.
- [ADR-024 — Interactive Pause and Resume](../architecture/adrs/ADR-024-interactive-pause-resume.md)
  -- the pause-and-persist substrate and the `resume_answer` contract this
  page walks through.
- [Interactive Pause/Resume Substrate](../architecture/components/interactive-pause-resume-substrate.md)
  -- the component page for the store the waiting record lives in.
- [How to use the readiness and approval gate](approval-gate.md) -- a
  different, non-resumable gate; not this page's subject.
