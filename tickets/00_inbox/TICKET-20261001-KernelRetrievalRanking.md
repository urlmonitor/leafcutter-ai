---
title: "Kernel: retrieval ranking quality, a regression benchmark and a design round before ranking"
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
risk_surface: cost
tags:
  - decision-kernel
  - retrieval
  - research
  - benchmark
last_updated: 2026-10-01
agents:
  python-coder: needed
  commit: needed
---

# Kernel: retrieval ranking quality, a regression benchmark and a design round before ranking

## Actor / Goal
In order to keep research cheap without losing the evidence that answers the question, we need an offline retrieval benchmark against the real repository first, and then a candidate ranking, a rerank loop, a synthesis rule and a design-decision ordering that fix the quality regressions round E introduced, so that later fixes can no longer trade quality for cost unnoticed.

## Context
Round E (V0.1, `feature/kernel-v01` @ cd2fd56c) made research cheap (one rerank batch per need) but the live regression on goals 5 and 2 and the round 7 decision run (run-6081b132e12d4214) show the quality got worse. Sources: the trace review `docs/analysis/2026-10-01-kernel-trace-review-decision-records-run.md`, the design docs `docs/analysis/2026-09-30-decision-kernel-design*.md` ("As built (V0.1 round E)"), and the inbox tickets KernelBudgetAwareDecisions, KernelSectionAwareRetrieval, KernelTargetedResearchQueries and KernelAnswerAwareCoverage.

Retrieval ranking (regression on round E, goals 5 and 2):
- N1 (high). `retrieval/pool.py` `merge_pool` fills the pool by RAW term hits: no length or density normalisation, no document-frequency weighting, no per-file cap, and the per-source guarantee shrinks to 1 slot with 6+ sources. Huge JSON/registry chunks (commit_guardian.json 191-217 hits, the test-angles flow JSON 211-263, agent_registry 52-66, long ticket comments, AC yaml) win the single 20-candidate rerank batch while the right items (design-3 section Persistence layout, `kernel/persistence/run_store.py`, the unit_tests and tests READMEs, design-6 section Test layout) sit at pool positions 24-34, unjudged. Fix: a length-normalised, document-frequency-weighted score (BM25-style, only to order the pre-filter, never a mandatory gate: spec section 17), a per-file cap in the pool, fair per-source shares, and "strongest not judged" on the same score.
- N3 (medium). `rerank.py` stops after the first batch as soon as any candidate passes the relevance bar. Fix: continue (up to `rerank_max_batches`, within budget and the decision reserve) until the need has enough strong items or the pool's remaining best score is clearly lower.
- N2 (high). Research hands evidence to host synthesis only when `evaluable` < 0.7, even when no need is satisfied and the answer judgements are under the bar (the same goal flipped between "9 findings" and "no findings"). Fix: decide synthesis from coverage as well (`research/executor.py`).
- N4 (low). The thin-coverage note does not name its need.
- N5 (low). `repo.registries` always skips `docs/build-dataflow.json` (812 KB > `max_file_bytes` 400000). Fix: a per-source byte limit, reported once.

Decision ordering (round 7 reached the ranked question in 7 calls but on 3 evidence items):
- R1. The design-judgement exit fires right after the first assessment, so the targeted, gap- and claim-driven research round never ran. Fix: one bounded targeted round (option claims, synthesis gaps, cited locators) within the budget reserve, then rank.
- R2. First-round decision research is too thin (1-3 items); `docs/components.json` was ranked out although the goal asks about component filters. Fix: raise the evidence floor and pin registry entries whose vocabulary the goal or criteria use.
- R3. The user's trace-review document was still the top item (0.80): the self-reference penalty only catches near-verbatim goal repeats. Fix: extend it to documents that review or analyse a kernel run of the same goal, conservatively, keeping them as context when explicitly cited.
- R4 (minor). The decision record's `design_reason` is null although `design_judgement` is recorded in state.

## Scope (no acceptance criteria by user decision)
- FIRST: an offline, deterministic benchmark in `tests/kernel/retrieval/` over the real repository (no Jev): the lexical pool and pre-filter up to the first rerank batch. Cases: goal 5 (kernel decision storage), goal 2 (where tests are saved), the decision-records goal, the second-domain cache scenario and lessons-file cases. The round E results are recorded as the "before" ratchet; every fix must improve the benchmark without regressing a case.
- N1 to N5 and R1 to R4 as above, each with a proving test, in this order: benchmark, N1/N3/N4/N5, N2, R3, R1/R2/R4.
- Config keys added or changed are listed in the commit messages and in the design doc's "As built (V0.1 round F)".

## Out of Scope
- Embeddings or any mandatory BM25 gate (spec section 17).
- A structured query mode for the AC store (a separate ticket).

## Comments
