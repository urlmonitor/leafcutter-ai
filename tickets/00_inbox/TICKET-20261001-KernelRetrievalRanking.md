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
  python-coder: signed_off
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

## Sign-offs
- [x] python-coder — 2026-10-01 14:11
- [ ] commit

## Comments

### 2026-10-01 14:11 — python-coder (status: ok)
feedback-id: fb_2026-10-01_0711575f
completion_manifest:
  benchmark_built_first_and_round_e_recorded: true
  n1_bm25_style_pool_ordering: true
  n2_synthesis_on_coverage: true
  n3_deeper_rerank_within_budget_and_reserve: true
  n4_coverage_note_names_its_need: true
  n5_per_source_byte_limit_and_named_oversized_file: true
  r1_one_targeted_design_round_before_ranking: true
  r2_evidence_floor_and_registry_pin: true
  r3_review_of_the_asking_run_demoted: true
  r4_decision_record_design_reason: true
  must_haves_the_lexical_score_cannot_reach:
    result: false
    reason: "design-3 section Persistence layout (pool 38), Stage-0 delta part 4 and concept parts 3 and 4 (outside the 60-candidate pool) and config/kernel_config.default.json are not reached in the first batch by any lexical ordering tried; run_store.py is at 28 and is judged in batch 2."
    remediation: "Semantic retrieval or a query expansion (store to persistence) is a separate change; the fixture keeps their pool positions as the gap."
Benchmark first (commit 03810b4b), then the ranking (a9bd8105) and the research and decision ordering (next commit). First-batch must-haves 4 of 14 before, 9 of 14 now; judged by the real loop with an oracle 6 of 14 before, 11 of 14 now; full kernel suite 1290 passed, 7 live skipped; live suite 7 of 7.

### 2026-10-01 17:03 — python-coder (status: ok)
feedback-id: fb_2026-10-01_f702d54f
Cross-platform defect (CI on Linux failed `lessons_approval_provenance` with 3 Jev calls against a ceiling of 2, while Windows passed at a09f9777). The cause was not the OS. Two parts of the environment leaked into the ranking:
1. `search_repo_text` counted words of the checkout folder's name as project words. In `worktrees/kernel-v01`, `kernel` was not a distinctive path word, so every `kernel/` section lost 3 x idf(kernel), about 15 points. CI checks out into `leafcutter-ai/`. This alone decided the failure.
2. The benchmark read files that git ignores. `build.py` installs `scripts/commit_guardian/`, `doc_compliance/` and `feedback/` as copies on Windows (no symlink rights) and as symlinks on Linux (never walked). That put 731 files into `repo.patterns` on Windows and 579 on Linux.

Fix: the kernel no longer uses the folder name, only the workspace id (`repository.py`, tested in `test_front_matter_and_ranking.py`). The benchmark scores only the files git does not ignore (`benchmark_support.py`, tested in `test_retrieval_benchmark.py`). With both fixes, Windows (`kernel-v01`, with build copies) and Linux (CI path) build an identical pool for every case.

Open (user decision): in that environment-independent ranking, `lessons_approval_provenance` needs 3 calls on both platforms. The recorded round F values came from the `kernel-v01` folder: positions 6 and 15, where both platforms now give 5 and 14. The ceiling of 2 is left unchanged, so the subtest fails identically everywhere until the baseline is re-recorded. Every other case is equal or better; for example, `run_store.py` moves from pool position 28 to 11 and is now in the first batch.

Resolved: on the orchestrator's decision, every case's round F `current` values were re-recorded from CI's checkout path with the fixed harness. `lessons_approval_provenance` now has a ceiling of 3 calls, and the improved positions and crowding are tightened; the round E baselines are unchanged.
