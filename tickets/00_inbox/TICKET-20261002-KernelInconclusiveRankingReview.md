---
title: "Kernel: when no option clearly wins, an LLM reviews the decision basis before the human is asked"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on:
  - TICKET-20261002-KernelResearchBeforeBlindEscalation.md
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: true
change_target: code
risk_surface: contract_boundary
tags:
  - decision-kernel
  - host-operation
  - decision-basis
last_updated: 2026-10-02
agents:
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: when no option clearly wins, an LLM reviews the decision basis before the human is asked

## Actor / Goal
In order that the human gets a ranking worth choosing from, we need the kernel to route an
inconclusive evaluation to an LLM. The LLM either hands back more or better criteria and context,
or names which context to pull in. The kernel then re-ranks, so the human is asked only once the
basis is as good as research can make it.

## Context
- **User requirement (2026-10-02, verbatim):** "If there is no clear winner, we should route in
  an LLM, which can take the evaluation and either hand back some more criteria / context or
  suggest which context to pull in."
- **Live reproduction:** run `run-aa2831ba7f0e4ec9`, decision `dec-1a74cadd0ecfbc9e`, Langfuse
  trace `cd514e662b611e8934dd7877eeded069`. The question was the storage format for reusable
  decision criteria.
  - Jev scored 5 options against 8 approved criteria.
  - Best required mean 0.77; no option reached more than 1 of 5 required criteria "likely met";
    three options reached none.
  - The kernel stopped at "design_judgement" after one research round and handed the human the
    ranked choice.
- **Context the kernel could not see:** ADR-065 (learned statistics are Neo4j aggregates,
  rebuildable, never canonical; review rejects "a statistic written into Git"). It was merged in
  PR #981 after the runtime checkout the run used (b0b5b7b9). It contradicts approved criterion 5,
  "the format carries usage and outcome counts". A reviewer pass is exactly what surfaces such a
  conflict.
- **Self-confirmation risk:** `host.generate_options` proposes options and criteria in ONE
  submission. Here the two generated options ranked #1 and #2 against criteria written in that
  same submission. The review must be a separate invocation that did not write the basis.
- **Prototype:** in the same session the step was run by hand. A fresh agent got the full
  evaluation and returned a diagnosis, criteria changes and context to pull in. The result is
  recorded in this ticket's Comments.
- **Today's free-text path:** a free-text answer at the ranked choice reaches Jev only as a
  constraint (`kernel/capabilities/decision/approvals.py` `_apply_design_choice`,
  `assess.py:89`). It cannot add criteria or trigger retrieval.
- **Related tickets:**
  - `TICKET-20261002-KernelResearchBeforeBlindEscalation.md`: research before a blind escalation.
  - `TICKET-20261002-KernelInterpretFreeText.md`: an LLM interprets human words.
  - `TICKET-20261002-KernelFindingsReachOptions.md`: in this run too, the options request carried
    `findings: []`.

## Scope (no acceptance criteria by user decision)
- **Deterministic "no clear winner" test** (config `decision.basis_review`): top required mean
  below a threshold, OR a gap between rank 1 and rank 2 below a threshold, OR fewer than N
  required criteria likely met by the top option. It is evaluated in `combine` before
  `_hand_to_human`.
- **New host operation** (working name `host.review_basis`) on the pattern of
  `kernel/capabilities/host/generate_options.py`. Its input is the question, options, criteria,
  the score matrix, cited evidence locators and findings. Its output:
  - a diagnosis;
  - criteria changes (add, reword, drop, change priority), all `proposed`;
  - context requests (retrieval queries or locators the kernel fetches through research, never
    the host);
  - option refinements, all `proposed`.
  - It carries no choice and no confidence.
- **Schemas** `leafcutter.basis_review_request.v1` and `leafcutter.basis_review.v1`. Conversion
  is total.
- **Effects:**
  - criteria and option changes go through the existing approval step (ADR-053 / ADR-060: the
    human approves);
  - context requests become research targets;
  - then assess and rank again.
- **Bounds and ending:** at most `max_basis_reviews` (default 1) per decision. A second
  inconclusive ranking goes to the human with the review's diagnosis shown in the question.
- **Registry descriptor and ADR:** dispatch `adr-author` directly with a pinned number.
- **Tests:**
  - an inconclusive matrix triggers the review; a clear winner never does;
  - proposed criteria wait for approval;
  - context requests become research targets;
  - the cap holds;
  - an integration replay of this run's matrix.

## Prototype result (2026-10-02, manual reviewer pass on run-aa2831ba7f0e4ec9)
A fresh agent got the evaluation and was told not to choose. It returned the five parts the host
operation should return. The main ones:
- **Diagnosis:** each required criterion bundled two or three claims. One required criterion (5)
  contradicts ADR-065. All five options left the same three things open: criterion/category
  identity, the approval and publish path, and where statistics live.
- **Missed evidence:**
  - ADR-065 and ADR-058 §3/§6.
  - The ADR-062 projector on `feature/knowledge-retrieval-v01`. It fails the Decision projection
    on any non-`dec-<16hex>` file in `docs/decisions/`, which counts against the "criterion kind
    in the decision store" option.
  - The validator in `kernel/memory/validate.py`, which validates every `*.yaml` in
    `docs/decisions/` as a decision.
  - A precedent the kernel missed: `dec-ef8ddcb79d668a67` has near-identical criteria but scored
    0.171 < `min_candidate_score` 0.3, because the precedent text score reads only the question,
    title and decision_type, never the criteria.
- **Criteria changes:**
  - Reword 6 of the 8 approved criteria.
  - Split criterion 5 into "outcomes left to the colony store" and "usage generated, not
    written".
  - Add `stable_identity`: decision-local ids already collide, `crit.small_slice` names three
    different questions in three records.
- **A combination option:**
  - Category records hold membership as (decision id, criterion id) references, so decision
    records stay unchanged.
  - SKOS-style labels: prefLabel / altLabel, broader, replaced-by.
  - Records are staged, then published by a human.
  - Usage comes from a generator; outcomes are Neo4j aggregates.
- **Context to pull in:** repository paths plus outside practice (SKOS primer, CSIRO SKOS best
  practice, MADR decision drivers, ISO/IEC 25010 as a seed vocabulary).
- **Open questions for the human:** six preference or authority questions.

Lesson for the build: the review's value came mostly from evidence OUTSIDE the decision's
retrieval set: unmerged branches, a newer main, and cross-record criterion comparison. The
review's context requests must therefore be able to name sources that retrieval did not rank.

## Out of Scope
- Splitting option generation from criteria generation in general (follow-up, if the review alone
  does not remove the self-confirmation risk).
- Reading Langfuse live (ADR-056 / ADR-057 §5 stand).

## Comments

## Implementation Tasks
### test-writer
- [ ] Trigger, approval, research-target, cap and replay tests listed under Scope.
### python-coder
- [ ] Config, trigger in `combine`, host op, schemas, effects, registry entry.
- [ ] ADR (pinned number), how-to and "As built" note.

## Risk & Safety
- Touches money? Bounded: one extra LLM host operation per inconclusive decision by default.
- Touches data? No; run artifacts only.
- Reversibility? Reversible; `max_basis_reviews: 0` restores today's behaviour.
