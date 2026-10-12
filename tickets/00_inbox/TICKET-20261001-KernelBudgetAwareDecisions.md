---
title: "Kernel V0.1 round E: budget-aware decisions, cheaper research, working criterion kinds"
status: in_progress
components:
  - decision_kernel
created: 2026-10-01
depends_on: []
priority: high
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
  - decision
  - retrieval
  - budgets
last_updated: 2026-10-01
agents:
  commit: needed
---

# Kernel V0.1 round E: budget-aware decisions, cheaper research, working criterion kinds

## Actor / Goal
In order to get the ranked human question the design-decision ending promises, we need a decision that reserves Jev budget for its own final assessment, research that is cheap enough to leave that budget, and a criterion-kind classification that actually fires for criteria about proposed designs.

## Context
Round 6 (live run `run-a522094b886048f3`, Langfuse trace `151abddee08230c8c651bcfa9fe35d92`, goal "Decide how Leafcutter should file decision records as JSON or YAML files under docs/ ...", default config) still never reached a human:

1. The run ended `blocked: jev call budget exhausted` at 40/40, three-quarters through the second decision assessment. 33 of the 40 Jev calls were retrieval reranks: after approval, targeted research fanned out into 8 needs (3 original + internal_principles + gap.1-3 + claim.opt.added.1), each reranking up to 60 candidates in chunks of 20 (about 3 calls per need). The no-progress and round-cap exits need a COMPLETED assessment, and the budget ran out first.
2. Jev classed all 6 criteria `evidence_answerable`; P(design_judgement) ranged 0.12 to 0.54 against the 0.7 threshold, even for "reviewable diffs", "readable by the knowledge-map parser" and "ids enforced at commit".
3. Retrieval details: concept part 3 was retrieved as front matter only (L1-14); `docs/components.json` is under no source root; option text produced the garbage explicit locator `-NNN.yaml`; `need.gap.2` was "satisfied" by one weakly related item; the round-5 trace review ranked top (0.88) only because it quotes the goal verbatim.
4. The blocked report said "Try rephrasing your request" for a budget stop.
5. Usage rows lost a call: 39 calls and a cost without the 40th (the completed half of the aborted assessment), while budget, envelope and trace said 40.

A live regression pass of five goals on the same code added: persistence evidence offered but never kept (cross-source round-robin cut, path-term ranking over content hits, front matter as evidence), partial coverage hidden behind a `completed` run, category-template filler in the content query, and a version-specific decline wording. Items D4 (evidence route follow-up) and D6 (ideas grounding) are separate tickets.

Sources: `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md`, the inbox tickets KernelDesignDecisionEnding, KernelTargetedResearchQueries, KernelSectionAwareRetrieval, KernelAnswerAwareCoverage, KernelJevAccountingTracing, KernelGateCalibration, and the design docs' "As built (V0.1)" notes.

## Scope (no acceptance criteria by user decision)
- E1 budget-aware ending: reserve the Jev calls of one final assessment (computed from the question count and `jev.max_questions_per_call`); research is not started, and is trimmed, when it would eat into the reserve; the ranked human question is built from the last complete assessment with a limitation that the ranking rests on limited evidence; an assessment is refused as a whole before its first call, never half scored.
- E2 cheaper research: `research.max_targeted_needs` 2, `retrieval.rerank_max_per_need` 20 (one call per need), explicit-locator hits are not reranked, decision-driven research plans exactly the categories the decision named.
- E3 criterion kind: literal true/false question with boundary examples and a deterministic backstop for criteria worded as questions about proposed options.
- E4 retrieval: front matter is never a section when a body exists, `docs/*.json` registries are a source root, explicit locators must be real files, a need is satisfied only by enough evidence above the bar, and a candidate that quotes the goal near-verbatim is demoted.
- E5 report text names the budget or guard that stopped the run and what the user can do.
- E6 usage rows and cost include provider calls completed before an abort.
- D1 to D3, D5, D7 and the decline wording from the regression pass.

## Out of Scope
- Calibrating the resolution gate (KernelGateCalibration).
- Evidence-route follow-up after synthesis unknowns (KernelEvidenceRouteFollowUp) and ideas grounding (KernelIdeasGrounding).
- Sharing one rerank batch across needs that hit the same sources (not done: the per-need cap already brings a need to one call).

## Comments
