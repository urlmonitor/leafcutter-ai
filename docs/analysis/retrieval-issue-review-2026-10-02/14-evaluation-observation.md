---
title: 14. Credible evaluation and observable diagnosis (S10 / P0.5)
description: Historical analysis and saved observations for 14. Credible evaluation
  and observable diagnosis (S10 / P0.5).
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# 14. Credible evaluation and observable diagnosis (S10 / P0.5)

Analysis only, 2026-10-02. Inspected code: `887c66d3896ba7727ce41b743887210a3883c6ce`. No implementation, AC/status edits, provider calls, database writes or remote tracing performed for this review.

## Finding and current evidence

Establish a complete, independently graded question-to-answer baseline through the existing kernel before claiming retrieval readiness. Preserve LangGraph run/wait/resume and existing observation ownership; no new orchestrator is needed.

The authoritative fresh receipts are [graph results](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md), [default-source results](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md), and [aggregate](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/aggregate.json):

| Lane | Actual behavior | Proof limit |
|---|---|---|
| Same graph-only canary | Both original questions enter research, then wait on population clarification; 8 real Jev calls, zero answers. RS-03 recognizes the literal ID but receives an irrelevant count-scope question. | Routing advanced; no graph query or completed answer. RS-02 may legitimately need population clarification, but the duplicated technical prompt is poor. |
| Actual default 15-source policy, backend `none` | Both collect native evidence and reach `waiting_host/synthesize_evidence`; 10 real Jev calls, zero answers, no host executed. | Supported handoff reached; evaluation stops before synthesis/resume. This is not the graph population stop or a Neo4j demonstration. |
| Direct controls | Eight active service facets grade correctly; historical controls pass 4/12, with eight prerequisite/projection mismatches. | No Jev selection or host quality established; historical failures are not eight newly observed incorrect answers. |

Aggregate: **18/24 authorized calls, four starts, two distinct scenarios, zero final answers, zero full target passes; 27/29 full journeys remain unrun.** Unused call allowance does not authorize another run. Three scripted starts establish control behavior only. Pagination receipts establish partial pages without exact totals; their helper's exit-1 serialization error remains separate from valid saved receipts. The earlier copied boundary-summary prompt warning has been corrected in current retest metadata; do not repeat it as an outstanding defect.

Code, source and publication are different identities: graph data remains `59269e024e4d0290b68b03d0d382745966e67e29`, mapper 7, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, semantic readiness false. Historical controls use mapper 3. Default native bytes came from an immutable Git archive at inspected code, with 10,498 unchanged file hashes; fresh analyst documents were absent.

Nevertheless, default RS-03 cites committed evaluation/oracle/catalog material, including `2026-10-02-retrieval-active-source-oracle.json`, and **does not cite canonical `KM-500c-2.yaml`**. This is observed benchmark leakage and an authority concern, not independent answer-quality proof. RS-02 has no complete population enumeration.

## Verified seams and limits

- `knowledge/evaluation.py::evaluate`, `_execute_case`, `_scope_judgments`, `_metrics` (20/166/138/199) execute actual retrieval or explicitly supplied assessment before grading; retain states, source identity, null quality for incomplete execution and `semantic_usefulness_proven=false`. Supplied assessment is not retrieval. Precision divides by unique returned IDs, not automatically requested k; document/recompute the denominator.
- `knowledge/evaluation_comparison.py::compare_reports`, `_compatibility`, `_measures` (12/73/119) bind comparisons to reviewed source/semantics/case scope and gates. `representative` is declared metadata, not independently established representativeness. Numeric gate validation currently checks numeric type, without explicit finite/range constraints: add discriminating validation tests before trusting promotion results.
- `tests/knowledge_live/retrieval_scenario_checks.py::live` (96) calls `KernelService.start_run` once and saves `RecordingTracer` output; it never supplies host or human resumes. A handoff counter is not a host execution counter. The existing Codex/Claude adapter contracts read only `input_artifact_refs`, perform the offered operation and resume with exact interaction/revision IDs.
- `kernel/scheduler/nodes_interaction.py::_packet_for` (62) calls `kernel/interaction/packets.py::write_input_artifact` (171). That writer applies runtime `Redactor.mask` to operational host evidence/context. `Redactor._mask_mapping/_apply_excerpt_policy` (148/163) applies **telemetry** excerpt policy to those bytes. Actual saved default-source host inputs contain `[OMITTED:excerpt]` under the deliberate `telemetry_excerpts=none` override. This demonstrates data-plane coupling under that setting. Unmodified default is `truncated` with 4,000 characters per field; its host usability was not tested. The coupling is a repair target, but zero answers here cannot be blamed on it: no host was run.
- `knowledge/observation.py::observe/fit_observation` (16/55) isolate sink failure and bound metadata. `integrations/knowledge_observation.py::observation_summary/RetrievalObserver._record` (22/81) separate execution, fulfillment and delivery. Local emission is `unverified`; only trusted matching remote readback can establish `verified`. Current local traces are not Langfuse proof and contain outbound fingerprints, not complete transmitted payloads.
- `integrations/knowledge_diagnosis.py::diagnosis` (14) projects the actual request/result, verifies trace identity matching and leaves underlying cause unknown absent a supplied violation. Its generic contract string and fixed next step are limited diagnostics, not a demonstrated complete incident investigation. Source inspection alone cannot prove an actual credential, network or transformation incident.

Read prompt constraints: `CLAUDE.md` and `templates/agents/{research-agent,test-writer,it-po}.md`. Use behavioral producer-consumer, real-artifact and discrimination proof, including a RED baseline. ITPO owns technical enrichment and must not rewrite BA criteria; this review only proposes reconciliation. The older reference document's after-coder ordering does not override current test-first prompt/repository rules.

## Options

| Option | Tradeoff |
|---|---|
| **A. Narrow completed canaries plus offline diagnosis controls (recommended)** | Repair blocking seams, then finish RS-02/03 in separate default/graph lanes. Smallest credible baseline; explicitly limited, not representative accuracy. |
| B. Add a reviewed held-out release benchmark immediately | Broader family coverage and measured gates; expensive and confounded while basic host/answer seams remain unresolved. Follow A. |
| C. Establish remote observation first | Useful ingestion proof, but cannot repair missing answers or contaminated evidence. Independent optional lane after local contract proof; never a prerequisite for retrieving evidence. |

## Smallest repair and evaluation sequence

1. Freeze receipt hashes and a machine-readable matrix of scenario, actor, source policy, prerequisites, stage, execution state, answer verdict and observation state. Keep all 29 dispositions, direct facets, historical cases and scripted controls separate.
2. Add RED producer-to-persisted-artifact-to-host-reader tests for the observed excerpt coupling. Separate mandatory secret/deny/authorized-content bounds from telemetry projection; telemetry `none/hash/truncated` must not silently replace required operational evidence. If disclosure policy withholds content, make it explicitly unavailable. Keep tracing equally restrictive; never reconstruct withheld inputs outside the packet.
3. Complete upstream exact-ID/population and root-answer obligation repairs in their owning slices. Extend the existing evaluation driver to consume real host submissions through `check_submission` and normal `KernelService` resume, retaining invalid/stale submissions and bounded stops. Record host input/output hashes, actor/model/version, latency/calls/cost and final report. Scripted host twins prove plumbing, not real synthesis quality.
4. Independently review canonical, source-pinned oracles before execution. For exact clauses require the canonical YAML field/locator; for counts define population and complete enumeration explicitly. Store held-out questions/expected answers outside searchable roots and every Jev/host input. Scan candidate/context packets for oracle/report fingerprints. Keep the actual-default leakage case as an unaltered diagnostic lane; label any corpus exclusions as a distinct clean benchmark configuration. Never silently call that modified lane default.
5. Under a separately prepared authorization boundary, run real Jev and a real host to terminal output using original questions without injected operations/answers. Ask genuine human clarifications; evaluator must not answer for the user. Grade evidence authority, exactness, completeness, citations and final fulfillment independently. Report completed answers/starts and full passes/29, selection correctness/eligible decisions, failures, waits, not-run, coverage, bytes, latency, tokens and measured/estimated costs separately. Choose reviewed thresholds from a representative baseline and lock held-out judgments before promotion.
6. Exercise local incident pairs and optional authorized remote readback separately. Correlate request/run/attempt/retrieval, expected/observed repository/revision/generation/query/permissions, evidence and contract locator. Unknowns stay unknown; next steps address evidenced limitations without expanding permissions.

## Existing ACs to reconcile, unchanged

Paths are under `docs/acceptance-criteria/knowledge-management/`; KM-500 entries live in `KM-500-research-capability-growth/`.

| Exact AC | Current work_status | Remaining proof or scope |
|---|---|---|
| KM-400c-5 | done | Preserve mechanics/semantic-quality distinction; no general real-quality claim. Located in `KM-400-trustworthy-project-knowledge/`. |
| KM-500a-4 | todo | Representative authorized real planning/selection, missing-prerequisite outcomes. |
| KM-500b-4 | todo | Actual coding agent produces, independently verifies, activates and resumes a missing query; not established by these starts. |
| KM-500c-2 | done | Reconcile original-question fulfillment with upstream answer-contract slice; transport success cannot satisfy it. |
| KM-500d-3 | in_progress | Independent representative baseline, held-out contamination controls, complete journeys and measured gates. |
| KM-500g-1 / KM-500g-1-i | in_progress | Matching finalized observation and loss isolation through root/host outcome; optional real remote verification remains unrun. |
| KM-500g-2 | in_progress | Matching-attempt diagnosis with known comparisons, contract citation and justified bounded next action. |

New host-content/telemetry separation and benchmark contamination requirements need explicit BA/ITPO contract reconciliation; do not assume these current statuses close them.

## Required RED and negative proof

- **Host artifact:** persist/reopen real input under all telemetry modes; a permitted distinctive clause survives to the real host consumer, secret/denied content does not. Missing/redacted/truncated clauses cannot be graded exact. Catch the current shared-redactor implementation.
- **Authenticity/completion:** stop at `waiting_host`, script an answer, substitute an oracle, duplicate resume, or submit foreign evidence; none becomes a real completed pass. Positive twin completes the same request through actual host output and final root consumption.
- **Prerequisites/scores:** missing Jev/host credentials or consent records not-run, zero unauthorized calls and null quality. Invalid score/confidence, NaN/infinity, wrong labels/distributions and absent answers traverse the real adapter/consumer and remain failed/unresolved. Reuse `jev_wire._number/_distribution/map_answers`; separately reject invalid evaluation gates and partial latency coverage.
- **Identity/leakage:** wrong SHA/generation/mapper, foreign repository, stale oracle, near-match AC and copied benchmark answer cannot pass canonical authority. An available oracle cannot fill absent actual fields.
- **Diagnosis/observation:** pair field omission with genuine unavailable retrieval; never infer zero records or credentials failure. Reject cross-attempt trace success, flush failure, forged URL and conflicting revisions; retrieval executes once. The opt-in live-observation test is a synthetic fixture plus remote readback, not Jev or production-incident proof; its existence is not execution.