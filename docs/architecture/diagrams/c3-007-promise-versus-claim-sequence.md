---
title: "Promise versus Claim — Where the Boundary to the Execution Observer Lies"
description: "L3 sequence diagram of the BP-1100g promise-versus-claim path: a plan promises a KIND of proof per acceptance criterion (the angle), a test writer answers with a test that CLAIMS that kind via a '# covers:' / '# angle:' tag pair, and the commit-time hand-off check refuses by name when a promised kind has no matching claim. Draws the boundary explicitly: the check reads exactly two authored declarations and never a test's body, so whether a test actually delivers what it claims is settled only by the execution observer (BO-2900a), which sits on the far side of the boundary with no message crossing into it."
type: architecture
diagram_type: sequence
status: active
flight_level: L3-Component
created: 2026-09-01
last_updated: 2026-09-01
parent: docs/architecture/components/phantom-done-prevention.md
source_ticket: null
components:
  - build_pipeline
  - testing_quality
  - documentation_system
related_docs:
  - docs/testing/test-angles.md
  - docs/architecture/components/phantom-done-prevention.md
  - docs/architecture/diagrams/c3-003-phantom-done-real-effect-intent-verification.md
  - docs/architecture/diagrams/c3-done-proof-evaluation-sequence.md
related_code:
  - scripts/commit_guardian/check_proof_promise_claim.py
  - scripts/ac_store/done_proof.py
  - scripts/commit_guardian/commit_guardian.json
  - config/ac_store_schema.json
tags:
  - phantom-done
  - test-angles
  - promise-versus-claim
  - declaration-not-evidence
  - BP-1100g
  - BO-2900a
---

# Promise versus Claim — Where the Boundary to the Execution Observer Lies

A **promised kind of proof** is answered by a **claimed kind of proof**. This diagram shows
that hand-off end to end, and — the reason it exists — shows exactly where it **stops**.

> **Read this first, or the diagram will mislead you.**
> The refusal drawn below does **not** prove the work is wired in. It proves only that a
> *declaration* was made to answer a *declaration*. A claimed kind of proof is a
> **statement about a test**, not evidence from one. The gate never looks at what the test
> actually does. The only thing that can settle that is on the far side of the boundary.

---

```mermaid
sequenceDiagram
    autonumber

    box rgb(232,244,253) DECLARATION SIDE — these participants exchange WRITTEN STATEMENTS only
        participant PLAN as Plan<br/>## Test Requirements<br/>(angle + covers)
        participant TW as test-writer
        participant TESTS as Test tree<br/># covers: / # angle:<br/>tag pair
        participant SCAN as collect_test_tag_records<br/>(done_proof.py)
        participant HOOK as check_proof_promise_claim<br/>(commit time)
        participant MAN as Sign-off record<br/>completion_manifest
    end

    box rgb(255,235,238) EXECUTION SIDE — the only participant that DERIVES anything from a RUNNING test
        participant OBS as Execution observer<br/>BO-2900a<br/>(watches the run)
    end

    rect rgb(232, 244, 253)
        Note over PLAN,TW: 1. THE PROMISE — the plan states the KIND, per criterion
        PLAN->>TW: for AC-N, a proof of kind 'angle' for this stated behaviour
    end

    rect rgb(237, 231, 246)
        Note over TW,MAN: 2. THE CLAIM — the test states the kind it gives
        TW->>TESTS: write test, tagged '# covers: AC-N' and '# angle: kind'<br/>on the SAME test function
        TW->>MAN: record the way in it resolved,<br/>and cross_layer_seam_answer (BP-1100g-5)
    end

    rect rgb(255, 243, 224)
        Note over PLAN,HOOK: 3. THE HAND-OFF CHECK — reads exactly TWO authored declarations
        HOOK->>PLAN: read the promised angle + covers values
        PLAN-->>HOOK: promises: ac_id, angle, behaviour
        HOOK->>SCAN: collect_test_tag_records(project_root)
        SCAN->>TESTS: ONE pass over TAG LINES only
        TESTS-->>SCAN: per-function records: covers, angles
        SCAN-->>HOOK: claim index: ac_id to claimed angles
        Note over SCAN: ADVISORY ONLY (BP-1100g-3-i).<br/>The angle axis feeds NO pass, done,<br/>or eligibility decision.
    end

    alt every promised kind has a matching claim
        HOOK-->>TW: "promised and claimed"
        Note over HOOK: Never worded reached / proven / verified / done.<br/>The claim is taken at FACE VALUE.
    else a promised kind has NO claim
        HOOK-->>TW: 4. THE REFUSAL — names the ac_id,<br/>the stated behaviour, and the missing kind
    end

    Note over PLAN,MAN: THE BOUNDARY IS HERE. Everything above is an authored declaration<br/>compared against another authored declaration. The check NEVER opens,<br/>parses, tokenizes, imports for inspection, or pattern-matches a test BODY.<br/>Swap a claiming test's body wholesale and the outcome is byte-identical (BP-1100g-4-i).

    Note over OBS: NO MESSAGE ARRIVES ON THIS LIFELINE.<br/>Whether a test DOES what it claims is settled ONLY by watching it run.<br/>That question lives here — outside this flow, and not answered by it.
```

Parent: [Phantom-Done Prevention — Real-Effect / Real-Intent Verification (Container Overview)](../components/phantom-done-prevention.md)

---

## How to read the boundary

The diagram is split into two participant boxes, and **that split is the point**:

| | Declaration side (blue box) | Execution side (red box) |
|---|---|---|
| Participants | plan, test-writer, test tree, scanner, hand-off check, sign-off record | execution observer (BO-2900a) |
| What it handles | authored text: `angle` values, `# covers:` / `# angle:` tag lines, manifest keys | the behaviour of a test **while it runs** |
| Arrows touching it | all of them | **none** |
| Can it tell a true claim from a false one? | **No** | Yes — that is the only thing that can |

The observer is drawn **because nothing reaches it**. An absent arrow between two drawn
participants states the limit of the gate more plainly than any paragraph: the correctness
question has somewhere to go, and this flow does not send it there.

## The four steps

1. **The promise.** A plan states, per acceptance criterion, which *kind* of proof it will
   produce — the `angle` value on each `## Test Requirements` descriptor. The seven kinds
   and their triggers are defined once in
   [docs/testing/test-angles.md](../../testing/test-angles.md); the single machine-readable
   source is `config/ac_store_schema.json`'s `test_spec[].angle` enum, taught to
   `test-writer` by **BP-1100g-1**.

2. **The claim.** A test states the kind it gives, via a `# covers: <ac-id>` and
   `# angle: <kind>` tag pair **on the same test function**. Both axes are collected in a
   single pass by `collect_test_tag_records` (**BP-1100g-3**) — one scanner, two axes, never
   a second walk of the test tree. A function carrying only one of the two tags contributes
   no claim for either axis alone.

3. **The record.** Alongside the test, the writer records how the way in resolved and its
   answer to the cross-layer seam rule — `cross_layer_seam_answer`, a sibling declaration on
   the same sign-off hand-off record (**BP-1100g-5**). It is a declaration too, on the same
   side of the boundary.

4. **The refusal.** At commit time `check_proof_promise_claim` (**BP-1100g-4**, registered in
   `commit_guardian.json`, run via `run_hook.py`) compares the promise set against the claim
   set and **blocks** when a promised kind has no matching claim, naming the `ac_id`, the
   stated behaviour, and the missing kind. The promise set is the denominator: a kind never
   promised is never demanded, and a plan that promises nothing is never refused.

## What the refusal does and does not establish

**It establishes:** a kind of proof that was promised for a criterion was also claimed by
some test function tagged against that criterion.

**It does not establish** — and must never be read as establishing:

- that the claiming test exercises the production entry point;
- that the claiming test is anything more than a pre-existing behaviour test that was handed
  a tag and otherwise left untouched;
- that the work is reached, wired in, proven, verified, or done.

**BP-1100g-4-i** pins this deliberately. A claim is taken at **face value**: the outcome is
byte-identical under a wholesale swap of the claiming test's body, and no part of reaching it
reads that body. This is why the success wording is the flat `"promised and claimed"` and
never `reached`, `proven`, `verified`, or `done` — so nothing downstream can quote it as
evidence that the work runs.

Reading a source scan into this gate would not fix that; it would make the gate itself the
failure mode it guards against (**BO-2900a-2**). A source scan inside a phantom-done guard is
phantom-done. The correctness question is therefore routed deliberately *out* of this flow,
to the execution observer that watches tests actually run — **BO-2900a**, which is not part
of this path and is not drawn as receiving anything from it.

## Acceptance criteria realised here

| AC | What it contributes to this diagram |
|---|---|
| `BP-1100g-1` | the seven kinds, taught from the `test_spec[].angle` enum |
| `BP-1100g-3` | the single-pass two-axis scanner, `collect_test_tag_records` |
| `BP-1100g-3-i` | the angle axis is advisory — it feeds no pass/done/eligibility decision |
| `BP-1100g-4` | the hand-off check and the named refusal |
| `BP-1100g-4-i` | the face-value rule: no test body is ever read |
| `BP-1100g-5` | `cross_layer_seam_answer` on the sign-off record |
| `BP-1100g-7` | this diagram |
| `BO-2900a`, `BO-2900a-2` | the execution observer and the prohibition that keeps the gate on the right side of the boundary |

## Cross-References

- [Phantom-Done Prevention — Real-Effect / Real-Intent Verification](../components/phantom-done-prevention.md)
  — the parent container page; owns the surrounding phantom-done guarantees.
- [Test Angles — A Set-Cover Taxonomy for Proof of Done](../../testing/test-angles.md) — the
  single definition of the seven kinds and the vocabulary this diagram labels its messages
  with. States the failure mode this boundary exists to make visible: *"a reachability
  mandate can still quietly be satisfied by a renamed `criterion` test."*
- [Phantom-Done Prevention — Proving a Durable Change by Real Effect and Intent](c3-003-phantom-done-real-effect-intent-verification.md)
  — the sibling L3 sequence for the BP-1100f gates (a different chain: real effect and stated
  intent, not promise versus claim).
- [Done-Proof Evaluation — Sequence Diagram](c3-done-proof-evaluation-sequence.md) — the
  fail-closed `# covers:` evaluation whose scanner BP-1100g-3 extended with the second axis.
