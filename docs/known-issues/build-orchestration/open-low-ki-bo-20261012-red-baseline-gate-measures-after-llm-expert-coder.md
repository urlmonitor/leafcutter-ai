---
title: "KI-BO-20261012-red-baseline-gate-measures-after-llm-expert-coder — /build-feature's red-baseline gate false-halts with green_at_baseline when llm-expert is the ticket's coder, because the gate fires before the first CODER_PHASES member and llm-expert is not one"
description: "medium — on run wf_86afbdc6-0a4 (TICKET-20261012-INF-800f-1) test-writer recorded a real red baseline of 9 failing tests, llm-expert implemented the work and handed off to python-coder, and the gate, which runs only before a python-coder / sql-coder / frontend-coder dispatch, measured after llm-expert had already turned all 9 green. It halted with green_at_baseline. A resume replayed the halt from cache in 42ms."
type: reference
category: reference
status: active
created: '2026-10-12'
last_updated: '2026-10-12'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261009-1833.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260907-resume-replays-cached-resolver.md
---

# KI-BO-20261012-red-baseline-gate-measures-after-llm-expert-coder — the red-baseline gate measures after llm-expert has implemented, so a real red baseline reads as green_at_baseline

> One known issue, filed on sight during the INF-800f-1 build (PR #1155, merged as
> `08879303`). Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The halt is loud and nothing wrong is committed. But the halt message
  states a TDD-order violation that did not happen ("All newly added tests are already green"),
  a resume cannot get past it, and every ticket whose coder is `llm-expert` and which later
  reaches a `CODER_PHASES` member hits the same measurement.
- **Status:** open, no AC.
- **Occurrences:** 1 (2026-10-12, run `wf_86afbdc6-0a4`, ticket `TICKET-20261012-INF-800f-1`),
  plus 1 resume that replayed the same halt.
- **First seen:** 2026-10-12 · **Last seen:** 2026-10-12
- **Where:** `templates/workflows-js/build-feature.js` on origin/main `b68d29679`:
  `CODER_PHASES = new Set(["python-coder", "sql-coder", "frontend-coder"])` (:1964); the gate,
  which fires only `if (CODER_PHASES.has(phaseName) && !redBaselineGateChecked)` (:2134-2148,
  commented "red-baseline gate runs ONCE before the FIRST coder dispatch"); `phaseOrder`, where
  `llm-expert` sits at priority 8, after `python-coder` at 6 (:422-431).

## Symptom

The run halts at `red-baseline-gate` with classification `green_at_baseline` ("All newly added
tests are already green") and `failing_phase: python-coder`.

The ticket says otherwise. Its `test-writer` sign-off carries a real `red_baseline` block: all 9
tests failing, for example "restructuring-specialist is not in config/agent_registry.json
agents[]".

## What happened

On `wf_86afbdc6-0a4` the agent order was `test-writer`, then `llm-expert`, then
`red-baseline-gate`.

1. `test-writer` wrote the tests and recorded the red baseline (9 of 9 failing).
2. `llm-expert` was this ticket's coder (`python-coder` was `not_needed`). It implemented the
   agent, then handed off to `python-coder` for one out-of-scope test edit.
3. The handoff made `python-coder` the next phase. `python-coder` is a `CODER_PHASES` member, so
   the gate fired before dispatching it. That was the first time the gate fired on this ticket,
   because `llm-expert` is not in `CODER_PHASES`.
4. The gate measured the tests after `llm-expert` had implemented them, saw all 9 green, and
   halted with `green_at_baseline`.

A resume replayed from cache and halted identically in 42ms. A fresh run got to later phases only
because `llm-expert` was by then `signed_off`.

## Detection

A `green_at_baseline` halt where the ticket shows both of these before the gate step:

- a `test-writer` sign-off with a `red_baseline` block listing failing tests, and
- an `llm-expert` sign-off.

## Workaround

Start a fresh run once `llm-expert` is `signed_off` (a resume replays the halt), or finish the
ticket by hand.

## Suggested fix

- Run the red-baseline measurement before the first implementing phase, whichever phase that is.
  `llm-expert` counts as the implementing phase when it is the ticket's coder.
- Or treat a `test-writer` `red_baseline` captured before `llm-expert` ran as the baseline, rather
  than re-measuring after it.

**Related.** `KI-BO-20261009-1833` is a different false halt of the same gate: there the gate
passed, but its verdict was lost to a 120s Bash timeout in the relaying agent. Here the gate
measured correctly, at the wrong moment. `KI-BO-20260907-resume-replays-cached-resolver` is the
same resume-replays-a-cached-result shape.

**Pattern:** a gate keyed on a fixed list of phase names, where the list leaves out a phase that
does the same job.
