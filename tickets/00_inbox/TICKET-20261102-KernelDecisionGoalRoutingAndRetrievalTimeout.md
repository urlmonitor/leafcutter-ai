---
title: "Kernel: explicit decision goals route without a one-choice question, and repository retrieval timeouts no longer end the run with no report"
status: todo
components:
  - decision_kernel
created: 2026-11-02
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - routing
  - retrieval
  - timeout
last_updated: 2026-11-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: explicit decision goals route without a one-choice question, and repository retrieval timeouts no longer end the run with no report

## Actor / Goal
In order to get a decision report for a goal that plainly asks for a decision, we need the
kernel to route such a goal to `decision` without asking the human, and to finish with
options, criteria and a decision (or an honest partial report) even when repository retrieval
is slow, so the host does not have to fall back to asking the user directly.

## Context
Observed 2026-11-02 on Windows 11. Kernel code at origin/main `8248ac7a` (runtime checkout
`worktrees/leafcutter-runtime`; `kernel/` is unchanged between `8248ac7a` and this branch's
base). Invocation: `python -P -m kernel run --input-file <goal.json> --json`, scope
`repository_root` = `C:/Users/Hendrik/Code/leafcutter/leafcutter-ai`.

Goal (verbatim):

> Decide how to fix the three test-writer eval checks that fail on report wording the
> test-writer template never asks for: drop the checks, widen them to accept equivalent
> wording, or add template sentences that ask for the wording.

The input also set `requested_output_schema: "leafcutter.decision_report.v1"` and supplied
`context.observations`.

Related: `TICKET-20261001-KernelIntakeIntent.md` (earlier intake/routing defects);
`docs/known-issues/build-orchestration/open-low-ki-bo-20261023-gate-verdicts-sensitive-to-machine-load.md`
(machine load changes timing-sensitive verdicts).

### Defect 1 - a one-choice routing question for an explicit decision goal
Both runs stopped at once with `waiting_human`:

> I am not sure how to handle this request: "Decide how to fix ...". Which of these fits
> best? You can also say it in your own words.

The only choice offered was `decision`. The goal starts with "Decide how to ...", names three
options, and asks for `leafcutter.decision_report.v1`; it should route to `decision` without
asking. A question with exactly one choice is not a decision for a human.

Code path (verified at `8248ac7a`):
- `kernel/scheduler/nodes_route.py` `_apply` (lines 265-285): any outcome other than
  selected / no_match / unavailable that is not split goes to `_unclear`.
- `kernel/scheduler/nodes_route.py` `_unclear` (lines 220-240): parks the item on
  `capability_question(goal, entry.report.semantic_candidates, ...)` with no check on how many
  candidates there are.
- `kernel/intent/questions.py` `capability_question` (lines 108-117): builds one choice per
  candidate, so a single eligible candidate yields a one-choice question.

### Defect 2 - repository retrieval times out and the run ends partial with no report
After the human answered "decision", both runs (`run-cd87dd99047e4540`,
`run-1652957b15594844`) logged, three times each:

```
WARNING kernel.scheduler.nodes_execute: capability retrieve.repository timed out after 120.0s
```

and also:

```
WARNING kernel.entity_index_read: entity policy deadline exhausted
```

Both ended with status `partial` and limitations:

```
work-…: unresolved_at_max_active_seconds: unnamed request
timeout: no result within 120.0s
```

No options, criteria or decision were produced; the host had to ask the user directly
(fallback). An earlier run the same morning (`run-c0b71afec3e34fc0`, goal "so what do we do
about the bad evals?") completed normally. Other agents and pytest were running on the
machine at the time, so load may be a factor.

Code path (verified at `8248ac7a`):
- `kernel/scheduler/nodes_execute.py` `_run_executor` (lines 120-128): wraps the whole
  capability in `asyncio.wait_for(..., timeout=limits.capability_timeout_seconds)`; on
  timeout returns a `timeout` failure with `no result within {timeout}s`, `retryable=True`.
  Any evidence gathered before the timeout is discarded.
- `kernel/capabilities/retrieval/executor.py` `_search_source` (lines 116-128): the
  knowledge-map search uses the same `capability_timeout_seconds` as its own inner timeout, so
  the inner and outer budgets are equal and the outer one can fire first.
- `kernel/entity_index_read.py` (lines 96-99): `entity policy deadline exhausted` returns an
  `unavailable` index view.
- `kernel/scheduler/guards.py` `unresolved_text` (lines 251-254): the limitation reads
  `unnamed request` when the work item has no goal, so the user cannot tell which step was cut.
- `kernel/config_sections.py` lines 59 and 63: `max_active_seconds` and
  `capability_timeout_seconds`. Three retries of 120 s retrieval (360 s) consume the
  active-time budget before decision work starts.

### Defect 3 (lower) - retrieval reads a stale repository root
In `run-c0b71afec3e34fc0` retrieval cited three known issues as open that were already
resolved on origin/main. `repository_root` was the main checkout
`C:/Users/Hendrik/Code/leafcutter/leafcutter-ai`, several merges behind origin/main. The
report gave no sign that its view of the repository was old.

## Expected behaviour
1. A goal whose request asks for `leafcutter.decision_report.v1` and reads as a decision
   ("Decide ...", named options) routes to `decision` without a human question.
2. The kernel never asks a routing question with exactly one choice: one eligible candidate
   is selected (or, if it is not acceptable, the item ends with a plain reason).
3. A slow retrieval returns what it found so far (a partial evidence result with a
   limitation) instead of an empty timeout failure, and the decision step still runs on that
   evidence, so the report has options, criteria and a decision or an honest
   `insufficient evidence` outcome.
4. Retries of a timed-out capability do not exhaust `max_active_seconds` before decision work
   starts.
5. Limitations name the step that was cut, never `unnamed request`.
6. (Lower) The report says which commit / how old the repository view is when the
   `repository_root` checkout is behind its upstream, or retrieval reads a fresh main.

## Acceptance Criteria
- [ ] AC-1: Given the verbatim goal above with `requested_output_schema:
  "leafcutter.decision_report.v1"` and a stubbed provider, when the kernel routes the root
  item, then it is bound to `decision` and no `human_question_request` is created.
- [ ] AC-2: Given a routing result whose `semantic_candidates` holds exactly one candidate,
  when `_unclear` would ask, then no question with one choice is created (the candidate is
  selected or the item ends with a stated reason); a test asserts no `RequestProposal` with
  `len(choices) == 1` is produced by `capability_question`'s callers.
- [ ] AC-3: Given a `retrieve.repository` executor stub that yields some evidence and then
  stalls past `capability_timeout_seconds`, when the run executes, then the capability result
  carries the evidence gathered so far plus a timeout limitation, and the decision step runs.
- [ ] AC-4: Given a retrieval that times out on every attempt, when the run ends, then the
  report status is `partial` with options/criteria or an explicit insufficient-evidence
  outcome, and `max_active_seconds` is not tripped by retrieval retries alone (retry budget is
  bounded below the active-time budget).
- [ ] AC-5: Given a guard trip on a work item without a goal, when limitations are written,
  then the line names the capability or step (e.g. `retrieve.repository`), never
  `unnamed request`.
- [ ] AC-6 (lower): Given a `repository_root` whose HEAD is behind its upstream tracking
  branch, when retrieval runs, then the report carries a limitation naming the HEAD commit and
  how far behind it is (or retrieval reads the upstream tree).

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |
| AC-6 | | | |

## Suggested direction
- Routing: before `_unclear` asks, select the single eligible candidate; and treat
  `requested_output_schema == leafcutter.decision_report.v1` plus a decision-shaped goal as a
  strong prior for `decision` (deterministic pre-check before Jev, or a routing feature).
- Retrieval: give the retrieval executor its own internal deadline below the outer
  `capability_timeout_seconds` and return partial evidence when it fires; make the knowledge
  map and entity index deadlines fractions of that budget, not equal to it.
- Retries: do not retry a `timeout` failure of the same capability with the same input more
  than once, or cap retry time against the remaining active-time budget.
- Limitations: pass the capability id into `unresolved_text` when the item has no goal.
- Load: record machine-load hints (wall vs CPU time) in the timeout limitation so slow runs
  under load can be told apart from real hangs (see the machine-load known issue).
- Stale root: compare `repository_root` HEAD with its upstream at run start and add a
  limitation; the fuller fix (reading origin/main) is a separate decision and may warrant its
  own ticket.
- Split: if this grows past one PR, split into routing (AC-1, AC-2), retrieval/timeouts
  (AC-3 to AC-5) and stale root (AC-6).

## Risk & Safety
- Touches money? No.
- Touches data? No; kernel run behaviour only. Changes to routing could bind a goal to the
  wrong capability, so AC-1/AC-2 tests must include a goal that should still ask.
- Reversibility: code-only, revertible.

## Comments
