---
title: "Kernel: a need counts as satisfied only when its evidence answers the question"
status: todo
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - retrieval
  - research
  - later-stage
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel: a need counts as satisfied only when its evidence answers the question

## Actor / Goal
In order to trust "need satisfied" in a research bundle, we need coverage to reflect whether the
collected evidence actually answers the question, not merely whether it matches the topic, so that
a run does not present topical-but-wrong evidence as an answer.

## Context
Coverage today follows judged relevance (retrieval keeps items whose relevance reaches
`retrieval.coverage_relevance_threshold`), and relevance is "is this candidate relevant to the
need". A dogfood run asked how decisions are stored today: `prior_decisions` was reported
`satisfied` by aspirational colony-memory design documents that discuss decision storage as a
future idea. The topic matched, the question "how are decisions stored today" was not answered,
and the bundle invited a false answer.

Governing text: Rev 3 spec sections 9.4 and 10.2 (needs are judged by bounded, literal questions;
research must not raise a score by collecting more of the same), ADR-053 (Jev for bounded
classification).

## Scope (no acceptance criteria by user decision; later stage)
- A per-need answer judgement: one bounded Jev noul per need, for example "does this evidence
  answer <the need's question>?", asked over the evidence that passed relevance, with the
  question and the evidence quoted as state (never as instructions).
- Coverage `satisfied` only when that judgement passes a configured threshold; otherwise
  `partial`, with a limitation that says the evidence matched the topic but did not answer.
- Cost kept bounded: one batch per research round, skipped when there is no evidence, thresholds
  and the on/off switch in configuration.
- Distinguish "describes the current state" from "proposes or aspires" where the question asks
  about the present, without domain-specific rules in code.

## Out of Scope
- New retrieval strategies (see the section-aware retrieval and structured-store tickets).
- Changing how decisions use the bundle.

## Comments
