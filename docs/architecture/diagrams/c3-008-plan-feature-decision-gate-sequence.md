---
title: "Plan-Feature Decision Gates — Where the Route Stops to Ask, and What Each Answer Costs"
description: "L3 sequence diagram of the five points at which the /plan-feature route stops and asks the person running it for a decision, and the three exits every one of those points has: an answer from the person and the run continuing; no person reachable and the run waiting on a record that outlives the process; and an answer that cannot be attributed to the person refused with the run still waiting. Exactly one path discards the drafted work, and it is the path the person chooses."
type: architecture
diagram_type: sequence
status: active
flight_level: L3-Component
created: 2026-09-14
last_updated: 2026-09-14
root: true
source_ticket: tickets/00_inbox/epics/EPIC-StartingNewWorkTheProperWayAlways/24_TICKET-20260826-ACD-2100e-1.md
components:
  - ac_driven_dev
related_docs:
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
  - docs/architecture/diagrams/c3-002-interactive-pause-resume-sequence.md
  - docs/architecture/diagrams/c3-001-interactive-pause-resume-run-lifecycle.md
  - docs/architecture/components/ac-driven-dev.md
related_code:
  - templates/workflows-js/plan-feature.js
tags:
  - ac-driven-dev
  - plan-feature
  - decision-gate
  - interactive-pause-resume
  - ACD-2100c
  - ACD-2100e-1
---

# Plan-Feature Decision Gates — Where the Route Stops to Ask, and What Each Answer Costs

The `/plan-feature` route stops and asks the person running it for a decision at
**exactly five points**. This diagram shows all five, and — the reason it exists — shows
that **every one of them has the same three exits**, only one of which throws work away.

> **Read this first.** The three exits are not five separate per-site behaviours that
> happen to match. They are a property of the **class** of human-decision point: a sixth
> point introduced later inherits all three with no per-site registration. That is why the
> exits are drawn **once**, around the whole set, rather than copied five times — copying
> them would depict five patches where the delivered mechanism is one rule.

---

```mermaid
sequenceDiagram
    autonumber

    actor P as Person running the route
    participant RT as plan-feature route
    participant ATTR as Answer-attribution check
    participant STORE as Pending-question record<br/>on disk (outlives the process)
    participant DRAFTS as Drafted work on disk
    participant AG as Non-person source<br/>(agent / default / stale reply)

    RT->>DRAFTS: steps before the decision point write drafted work
    Note over RT,DRAFTS: THE CLOSED SET — the route presents exactly these five decision points<br/>and no others: (1) approve a drafted product-truth artifact — (2) approve the<br/>mid-pipeline authoring stage — (3) give final approval — (4) choose how to<br/>proceed when the request looks already covered — (5) decide what to do with<br/>stranded drafts from an earlier run.

    loop ONCE PER DECISION POINT — for each of the five named above
        RT->>P: ACD-2100c-1 — put the question on the channel<br/>that reaches the person
        Note over RT,AG: ACD-2100c-1 — NO dispatch is made to obtain this answer.<br/>The guard is on the CLASS of human-decision point, not on a list of five:<br/>a sixth point added later inherits all three exits with no registration.

        alt EXIT 1 of 3 — the person answers (ACD-2100c-1)
            P-->>RT: answer, carrying the channel it arrived on
            RT->>ATTR: does this answer come from the person?
            ATTR-->>RT: yes — attributed to the person
            alt the person's answer continues the run
                RT->>DRAFTS: drafted work kept; run proceeds past this point
            else the person chooses to stop (ACD-2100c-5)
                RT->>DRAFTS: THE ONLY DISCARD IN THIS DIAGRAM —<br/>drafted work is thrown away
                RT->>STORE: record the PERSON as the source of that choice
            end
        else EXIT 2 of 3 — no person is reachable (ACD-2100c-2)
            RT->>STORE: write a record naming this run and this decision point
            STORE-->>RT: persisted — survives after the process exits
            RT->>P: reports: waiting for an answer
            Note over RT,DRAFTS: No step after the decision point runs. Drafted work is still<br/>on disk, unchanged. NOT recorded as the person having chosen to stop.
        else EXIT 3 of 3 — an answer that is not the person's (ACD-2100c-4)
            AG-->>RT: well formed, names a real choice —<br/>but did not come from the person
            RT->>ATTR: does this answer come from the person?
            ATTR-->>RT: NO — refused; the choice it names is not carried out
            RT->>STORE: run stays at THIS decision point, still waiting
            Note over RT,DRAFTS: Reason recorded is "did not come from the person",<br/>NOT "could not be understood". Drafted work retained.
        end
    end
```

---

## The five decision points

The route asks the person for a decision at these points and **no others**:

| # | The decision |
|---|---|
| 1 | Approve a drafted product-truth artifact |
| 2 | Approve the mid-pipeline authoring stage |
| 3 | Give final approval |
| 4 | Choose how to proceed when the request looks already covered |
| 5 | Decide what to do with stranded drafts from an earlier run |

Points 4 and 5 are the two most often forgotten, and point 5 is the one that can **delete
drafts** — which is precisely why the closed set is stated rather than left implied.

## The three exits, and why they are drawn once

Every one of the five has all three of the exits below. None of the five has a fourth.

| Exit | Trigger | Where the run ends up | Drafted work | Criterion |
|---|---|---|---|---|
| 1 | The person answers | Continues past the point — **or** stops, if that is the answer | Kept, **unless** the person chose to stop | `ACD-2100c-1`, `ACD-2100c-5` |
| 2 | No person reachable | Waiting, on a record that outlives the process | Kept, unchanged | `ACD-2100c-2` |
| 3 | An answer not attributable to the person | Still waiting, at the *same* point | Kept | `ACD-2100c-4` |

The exits are drawn once around the whole set because the mechanism is class-wide. The
acceptance test for `ACD-2100c-1` is explicit about this: a **sixth** human-decision point
introduced into the run is put on the person's channel and produces no dispatch *without
any per-site registration*. Five passing per-site assertions would look identical to a
solved problem while being five patches; the single enclosing rule is the delivered thing.

## Only one path discards the work

Of the four ways a run can leave a decision point, **exactly one** ends with the drafted
work thrown away: the person chooses to stop. This is `ACD-2100c-5`, and it has two halves
that must hold together:

- When the run ends for **any other** reason — no answer arrives, the channel is
  unavailable, or an answer arrives that cannot be attributed to the person — the drafted
  work is **still on disk after the process exits**, and the run does **not** record the
  outcome as the person having chosen to stop.
- When the person **does** choose to stop, the work is discarded **and** the run records
  the person as the source of that choice.

Attributing a stop to a person who never chose it is a recorded claim the run did not
establish — the same false-green shape this repository exists to prevent, one level up.

## Why an answer can be refused while being perfectly well formed

Exit 3 is the non-obvious one. The refused answer in the diagram is **well formed** and
**names one of the choices the decision actually offers**. It is refused purely on
**provenance** — it did not come from the person. `ACD-2100c-4` pins both halves: the
reason recorded must be that the answer did not come from the person, *not* that it could
not be understood; and an answer identical in every respect **except** that it did come
from the person is accepted and carried out.

This is why the non-person source is drawn as its own lifeline. Its answer reaches the
route and is turned away at the attribution check — the arrow exists, and it never becomes
an accepted decision. An agent supplying an answer is depicted **only** as the thing that
gets refused.

## What this diagram is not

It does not show **how** a pause is mechanically effected — the persist/read exchange, the
pending-question store's internals, or resumption by run id. That substrate is ADR-024 and
is documented in its own two diagrams, linked below. This page is about **which** decisions
the route stops at and **what each exit costs**; the substrate is about the machinery a
pause runs on. Read them together, not instead of one another.

## Acceptance criteria realised here

| AC | What it contributes to this diagram |
|---|---|
| `ACD-2100c-1` | the closed set of five decision points, the person's channel, and the no-dispatch rule |
| `ACD-2100c-2` | Exit 2 — the durable record, the run reporting that it waits, drafts untouched |
| `ACD-2100c-4` | Exit 3 — refusal on provenance, the run still waiting at the same point |
| `ACD-2100c-5` | the single discard path and the person recorded as its source |
| `ACD-2100e-1` | this diagram |

## Cross-References

- [AC-Driven Development](../components/ac-driven-dev.md) — the component page for the
  route whose decision points this diagram depicts.
- [ADR-024 — Interactive Pause and Resume](../adrs/ADR-024-interactive-pause-resume.md) —
  the contract that gives Exit 2 somewhere to go when no person is reachable.
- [Interactive Pause/Resume — Sequence](c3-002-interactive-pause-resume-sequence.md) — the
  substrate at message level: `resolveGate`, the persist/read exchange, the pending-question
  store, `resumeFromRunId`. Linked rather than restated.
- [Interactive Pause/Resume — Run Lifecycle](c3-001-interactive-pause-resume-run-lifecycle.md)
  — the same substrate as a state machine (`running` → `paused_awaiting_input` → `resumed` /
  `nothing_to_resume` / `unresumable_stale`). Linked rather than restated.
