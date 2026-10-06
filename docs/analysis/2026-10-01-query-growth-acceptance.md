---
title: Query growth acceptance reconciliation
description: Final per-criterion evidence and limits for KM-500 research capability growth.
type: explanation
status: active
created: '2026-10-01'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# Query-growth acceptance - 2026-10-01

The nine KM-500 implementation leaves are accepted for the bounded implemented behavior and marked `done`. Ticket delivery remains separate until commit/release gates finish. KM-400 behavior and parent product criteria are unchanged. Live external Jev validation remains **not run**, pending explicit approval for the provider request; it is not represented as passing.

## Measured evidence

- **15 passed in 10.33s**: `test_query_growth_kernel.py`, `test_query_growth_adversarial.py`, `test_query_growth_boundaries.py`, explicit `-o addopts= -p no:cacheprovider`. Real KernelService/SQLite scheduling, human/host continuation and durable catalog work are exercised. Jev, candidate creation and the database execution seam are scripted in these tests.
- **333 passed, 153 subtests passed in 18.79s**: integration lead final broad run covering the three growth test files plus kernel config, contracts, registry, capabilities and bootstrap. Its focused growth rerun also passed 15 tests in 9.93s.
- **67 passed, 6 subtests passed in 53.61s**: independently rerun existing `test_research_graph.py`, `test_restart_resume.py`, `test_fixb_ledger.py`, `test_guards.py` and `test_gap_no_fallback.py`. Exact inherited test nodes are linked in the relevant ACs. These establish research contradiction/insufficiency handling, bounded synthesis, shared budgets, replay/crash recovery and denial/outage distinctions.
- **2 passed in 1.20s**: implementation lead's actual local Neo4j 5.26 checks in `tests/knowledge_live/query_catalog_checks.py`. Synthetic scoped graph fixtures exercise compiled two-hop Cypher, independent admission, catalog reopening, public retrieval, eleven-neighbor saturation returning `partial`, and genuinely completed empty results returning `ok`.
- **1 passed in 8.27s**: `test_aura_query_growth_public_proof`, actual Aura and committed source `9f70de80ebcafe59ff55cce6732deb92069f9541`. Report: `reports/knowledge-query-growth-aura.json`. A fresh isolated persistent catalog verifies build and activation on every proof run. The same research resumes after verified admission; reopened checkpoints and a fresh run reuse the persistent catalog. Every selected source SHA, original goal, need coverage and explicit partial-result limitations are asserted. Jev is scripted and the candidate is BA-authored. The report records three evidence items, both runs `partial`, zero provider/embedding calls and no database writes. Local catalog persistence is intentional.
- Neutral catalog tests separately prove malformed candidates, tamper rejection, timeout/cancellation, atomic version admission and subprocess catalog discovery. Their database double does not prove Cypher correctness; actual Neo4j checks above provide that evidence.

Independent review first captured regressions for an unmapped memory relationship appearing empty and human arguments escaping component scope. Both were corrected before final checks. Alternate verified versions cannot substitute for the submitted candidate at resume.

## Per-leaf verdict

| AC | Accepted observable behavior and evidence |
|---|---|
| KM-500a-1 | Focused missing-input clarification; same continuation resumes without query/build before the answer; scalar clarification preserves original/effective questions, source and query digest. Existing provider-error and bounded judgment handling are reused. |
| KM-500a-2 | Catalog exposes input/purpose/question metadata; explicit typed requests retain deterministic validation; semantic selection is bounded to catalog choices and records selection provenance. Missing scalar inputs return to clarification. Actual fresh-run catalog reuse is demonstrated. |
| KM-500a-3 | Unsupported requested source kind stops before query selection/build; kindless unsupported memory edges are rejected; empty, partial, unavailable, denied and exhausted outcomes remain distinct. Actual Neo4j verifies partial versus completed-empty behavior. |
| KM-500b-1 | Canonical gap and coding-host child retain original need/source; packet includes catalog, expected result and bounded budget metadata. Existing scheduler reserves shared host budget before dispatch rather than inventing a remaining balance. Source-kind positive/negative tests verify eligibility before packet creation. |
| KM-500b-2 | A genuinely new two-hop recipe compiles to parameterized scoped Cypher; strict language, expected-result cases, injection/isolation, limits and cancellation are checked. Real Neo4j and Aura execute the authored query. The independent source judgments are distinct from candidate-authored expected outputs. |
| KM-500b-3 | Atomic local catalog activation, retained digests, reopen integrity and fresh-process discovery work. Actual scheduler permission denial leaves catalog unchanged and cannot trigger another host fallback. Reverification retains source binding; tampering and stale versions fail closed. |
| KM-500c-1 | Original research/checkpoints resume after matching verification; source/need/query digest survive. Wrong same-operation versions are rejected. Aura demonstrates actual retrieval and fresh-run reuse; inherited ledger/crash tests establish at-most-once delivery. |
| KM-500c-2 | Evidence retains actual source revision; registration does not itself answer the question. Actual Aura runs remain honestly partial. Existing public research tests preserve contradictions, unsatisfied needs, failed-source limitations and bounded synthesis without replanning. |
| KM-500c-3 | Repeated failed delivery remains failed; exhausted build/clarification emits no new child. Existing public scheduler tests establish shared budgets, bounded repair through restart and recovery only with new evidence. |

## Evaluation limits

`reports/knowledge-query-growth-source-judgments.json` independently reads canonical YAML at the committed source: `git_vcs_operations` has eight ACs and four directly declared test files; `release_manager` has one AC and no direct test reference. The stored candidate uses these positive/empty judgments. This query answers which test files are directly declared for component ACs. It does not prove those tests pass, infer undeclared coverage, or establish general semantic usefulness. No fabricated semantic scores are reported.

The recipe language remains bounded. Unsupported grammar is an explicit code-build limitation. The live provider test is separately pending authorization; scripted Jev exercises control flow, not real model decision quality. Final commit hooks and release state are separate from this behavioral acceptance.

## Native-branch repeatable CI proof - 2026-10-02

The following records the implementation merged from native branch commit
`4f5643d9`; it is historical branch provenance, not the integrated path below.

At that native-branch revision, the required AC links pointed to `test_local_query_growth_public_proof` in
`tests/knowledge_live/query_growth_checks.py`. It publishes a tiny synthetic,
committed Git corpus to an isolated loopback Neo4j service and exercises the real
projection, generated Cypher, verifier, catalog, kernel continuation and reopened
checkpoint. Jev and host delivery are scripted. The query-only scenario explicitly
disables optional host synthesis and asserts that bounded evidence remains
partial; the existing research tests retain the synthesis-policy coverage.

This makes the proof repeatable without hosted credentials, a particular Aura
retention window, or Windows-only environment paths. The historical Aura result
above remains pinned to its recorded source and is not refreshed by the local
check. The supplemental hosted probe is now an explicit callable:
`run_aura_query_growth_public_proof()`, with `LEAFCUTTER_RUN_AURA_QUERY_LIVE=1` and
configured Aura read credentials required. It shares the same scenario and writes
its own labeled report only after a successful hosted run.

## Integrated retrieval proof path - 2026-10-02

The integrated release retains `tests/knowledge_live/query_growth_local_checks.py::test_local_query_growth_public_proof`
for these four ACs. It uses real local Neo4j and public kernel continuation,
consumes the configured synthesis packet with source-citing controlled findings,
and verifies bad-candidate refusal, persisted verification digests and fresh
catalog reopening. It retains the repository synthesis default. Scripted actors
do not establish live semantic usefulness. The separate historical hosted entry
`test_aura_query_growth_public_proof` in `query_growth_checks.py` remains manual
and requires explicit Aura authorization; it is not automatic completion coverage.
Neither path refreshes or relabels the earlier hosted receipts.
