---
title: Retrieval scenario evaluation results
description: Independent review of actual retrieval outputs, controlled kernel runs and unimplemented target scenarios.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# Retrieval scenario results — 2026-10-02

The current graph returned correct bounded facts in the eight fresh service probes. The 29 proposed scenarios are **not 29 executed end-to-end tests**: none has a demonstrated complete target-flow pass. Two question-only kernel scenarios were probed with scripted Jev; the remaining observations use explicitly selected operations or older evaluation controls. Two authorized real-Jev starts both stopped at initial capability routing, before retrieval. They returned no answer; retrieval planning and evidence-judgment quality remain untested.

This report independently grades saved outputs against the [29 scenarios](2026-10-02-retrieval-scenarios.md), [feasibility map](2026-10-02-retrieval-scenario-execution-map.md) and [fresh immutable-source oracle](2026-10-02-retrieval-active-source-oracle.json). It does not modify implementation, acceptance criteria or lifecycle status.

## What actually ran

| Run | Actual surface and actors | Result and qualification |
|---|---|---|
| Eight active-source probes | Public `KnowledgeService.retrieve`, actual read-only Aura; no Jev. Named withholding/clipping/outage controls use the existing boundary adapter. | Eight reviewed bounded outcomes are consistent with their requested facts or deliberate refusal conditions. They cover facets of ten RS cases, not ten complete scenarios. |
| Twelve retained evaluation cases | Existing evaluator against retained source `9d115947…`, mapper 3; original assertions preserved. | **4 passed, 8 failed**. This replay does not reproduce the newer projection prerequisites of the earlier successful evaluation. It is not evidence of eight fabricated answers or eight current-generation regressions. |
| RS-02 question-only research | Actual `KernelService.start_run` and Aura composition, scripted Jev, local recording tracer. | `waiting_human`; no invented count. Clarification wording has usability defects; no human answer/resume was executed. |
| RS-03 initial negative control | Same real kernel, script selected unoffered `get_entities`. | Correctly rejected with `invalid_request`; empty partial bundle. This was an invalid harness selection, **not failure of a supported selected query**. |
| RS-03 allowed-choice control | Same question, script selected offered `clarify`. | `waiting_human`, requesting a component ID. Proves allowed-choice handling, not that a real model would make that choice. |
| Two real-Jev canaries | Actual RS-02/03 requests to `api.typesafe.ai`; resolved model `jev-1.13.0`. | **Both waiting_human at initial routing; zero retrievals/answers.** One call each, 2 of the authorized maximum 24. No retries, resumes, graph writes or remote trace export. |

Raw evidence: [active outputs](../../reports/retrieval-scenarios-2026-10-02/active-controls.json), [historical replay](../../reports/retrieval-scenarios-2026-10-02/historical-controls.json), [kernel probes](../../reports/retrieval-scenarios-2026-10-02/kernel-controls.json), [allowed-choice probe](../../reports/retrieval-scenarios-2026-10-02/kernel-valid-controls.json), [live boundary](../../reports/retrieval-scenarios-2026-10-02/live-boundary.json), [code fingerprint](../../reports/retrieval-scenarios-2026-10-02/code-fingerprint.json).

The active source is `59269e024e4d0290b68b03d0d382745966e67e29`, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, mapper **7**, semantic readiness **false**. Execution code includes uncommitted merge/worktree changes; the saved fingerprint identifies those bytes. Source revision, execution code and historical test revision are different identities. No graph publication or semantic-provider readiness is implied.

## Real Jev: both requests stopped before retrieval

The independent review inspected both [RS-02 live output](../../reports/retrieval-scenarios-2026-10-02/RS-02.live-response.json) and [RS-03 live output](../../reports/retrieval-scenarios-2026-10-02/RS-03.live-response.json), including local provider-generation traces and `routing.assessed` events. Configured `jev-latest` resolved to `jev-1.13.0`. Each made exactly one successful provider call; this was neither a transport error nor an exhausted 12-call budget.

| Case | Actual provider judgment | Actual system outcome | Independent verdict |
|---|---|---|---|
| RS-02 | Selected `research`; probability 0.67, confidence 0.51. | Routing recorded `insufficient_context` / `low_confidence`; `waiting_human`, output null, no evidence. | Did not reach the required focused population clarification. No false count, but asking the user to select an ability is not the scenario's intended question handling. |
| RS-03 | Selected `research`; probability 0.58, confidence 0.36. | Same low-confidence routing wait; output null, no evidence. | Exact known-ID question was not answered and never reached the graph. This is an observed routing/usability failure to progress, not a Neo4j answer error. |

For RS-03 the actual user-facing message was:

> I am not sure how to handle this request: "For KM-500c-2, what must tests demonstrate?". Which of these fits best? You can also say it in your own words.

The only displayed capability choice was `research`, with a truncated description. RS-02 received the equivalent ability-choice message for its original question. Neither interaction asked the material count-population question. Both preserve a human wait rather than fabricating findings; no human response was supplied. The observed cause is the low-confidence routing gate recorded in the trace. This small sample does not establish whether the appropriate repair is prompt context, routing policy, calibration or a typed-entry bypass; lowering a threshold blindly is not justified by these two runs.

No graph read was reached during these live starts, so their authorized repository-evidence transfer allowance was not used for retrieved excerpts. The eight separate Aura service probes remain the evidence for graph facts. Live output contains local trace IDs but no verified remote trace URL.

## Actual returned facts and failures

**Complete count (RS-05/20 facet).** The translated typed request asked for TQ-500f L2/L3 descendants, excluding only the root, with `work_status` and complete enumeration. The actual output was:

```json
{"status":"ok","answer":{"status":"fulfilled","completeness":{"complete":true,"known_count":15,"exact_total":15},"work_status_counts":{"done":5,"todo":10}}}
```

This excerpt selects actual fields; the raw receipt retains the entire response. Independent review matched **all 15 IDs, work statuses, levels and file content hashes** against separately archived Git bytes. Eleven terminal leaves would be a different population. These numbers do not mean all repository requirements about test writing.

**Missing field (RS-19 facet).** With `work_status` deliberately withheld, execution remained `ok` but answer status became `partial`, `work_status_counts` was `null`, and all 15 missing fields were listed. Population completeness remained true: membership was known, but status grouping was not. The system did not substitute lifecycle `status` or the independent oracle's counts.

**Exact clauses (RS-03/22 facet).** Direct lookup returned KM-500c-2's canonical `/criteria`, correct file/source attribution and scalar SHA-256 `9cfea912e97757a50beaab42e39ccfd82dd6f2bbf0d6e9425daf3e1d9e2617d3`. It includes: “a successful build, successful query execution and successful answer assessment remain separate recorded outcomes.” This is a structured evidence response, not a generated conversational answer.

**Dependencies and partial limits (RS-11/15/27 facets).** Direct incoming dependencies returned exactly `TQ-500f-2-i`, `TQ-500f-2-ii`, `TQ-500f-3-i`, `TQ-500f-5`, `TQ-500f-6`. The four-result control returned `partial`, `truncated=true`, `known_count=4`, `exact_total=null`. Clipped criteria likewise stayed partial. Neither proves adaptive traversal or exhaustive code impact.

**Unavailable and observation limits (RS-25/28 facets).** The deliberate outage returned `unavailable`, unresolved answer, no evidence and no exact total. The withheld-field observation probe returned `observation.state=disabled` and `assessment=null`. It demonstrates honest missing-field reporting, **not** an incident diagnosis, verified remote trace or learned strategy record.

**Question-only clarification (RS-02).** Actual question: “How many ACs concern test writing? Exclude parent requirements.” The returned prompt begins “Please supply the missing population choices: population, population” and asks for JSON with `scope` and optional `required_fields`, while the interaction advertises `structured_allowed=false` and free text. This is a technical, repetitive clarification rather than a focused user-facing choice. The contradiction is in the interaction presentation; JSON text might still be accepted as free text, which was not tested here. No population was silently assigned and no count was invented.

**Exact-ID catalog gap (RS-03).** Actual question: “For KM-500c-2, what must tests demonstrate?” The offered graph-query catalog lacks `get_entities`, although that direct operation successfully returns the criterion. The initial script wrongly selected it; correct rejection is not a product execution bug. A second script selected the allowed `clarify` option and received “Which project component should I research? Give its component ID…” despite the question naming an AC. This exposes the current menu/clarification limitation under a controlled choice; it does not measure autonomous Jev judgment. A semantically valid exact-ID selection through this offered menu was not demonstrated.

## All 29 scenario dispositions

“Facet correct” means the narrower saved observation is correct, not that the complete target scenario passed. “Absent” identifies target orchestration missing from the current route. All full target-path verdicts below are **not demonstrated**.

| RS | Observed answer or facet outcome | Complete-path gap / unrun obligation |
|---|---|---|
| 01 | Not executed for its original question. | Question-only search/navigation choice and answer not exercised. |
| 02 | Live: ability-choice wait before retrieval, not focused population clarification. Scripted: count-scope wait with technical wording. | Live target fails to progress to intended clarification; human resume not exercised. |
| 03 | Live: low-confidence ability-choice wait, no answer. Direct clauses correct; invalid script correctly refused. | Live routing blocks before graph; exact lookup also absent from controlled offered menu. |
| 04 | Not run. | Automatic advisory applicability/reuse absent. |
| 05 | Count/field facet correct in active RQE-01-P. | Jev choosing between fitting/misleading contracts untested. |
| 06 | Not run. | Generic typed argument-preparation handoff absent. |
| 07 | Not run. | Target known-keyword bypass/shared comparison absent. |
| 08 | Not run. | Optional five-term LLM handoff absent. |
| 09 | Not run. | Target keyword/vector portfolio comparison absent; active semantic source not ready. |
| 10 | Not run. | Useful sibling preservation across the specified two methods untested. |
| 11 | Five direct declared dependents correct. | Interactive Jev frontier navigation absent. |
| 12 | Not run. | Offered code-folder/file traversal absent. |
| 13 | Not run. | Frontier cycle/checkpoint and multi-axis budgets absent. |
| 14 | Not run. | Target stale/escaped observed-file refusal path absent. |
| 15 | Partial-page facet correct; no exact total. | Target traversal coverage/continuation absent. |
| 16 | Older proof-assessment replay lacks expected declarations under mapper 3. | Traversal-to-new-method/advisory transition absent. |
| 17 | Not run. | Common observed-attempt comparison absent. |
| 18 | Not run. | Shared cross-method provenance-preserving combination absent. |
| 19 | Missing work-status facet correct; counts withheld. | Main target assessment path not executed. |
| 20 | Exact active-source 15/5/10 facet correct. | Target combination/all-page orchestration not executed. |
| 21 | Not run. | Specified wording acceptance and merge-trigger evidence not exercised. |
| 22 | Direct structured criterion/locator facet correct. | Target conditional wording-bypass transition not executed. |
| 23 | Retained mapper-3 fitness controls return unknown, build ineligible. | Three-state current-manifest comparison/build routing not exercised. |
| 24 | Not run in this evaluation. | Build dedup/admission/resume/common comparison untested here. |
| 25 | Deliberate outage correctly unresolved. | Alternate-method continuation/all-routes control absent. |
| 26 | Not run. | Policy clarification after retained evidence untested. |
| 27 | Clipped criterion/four-result facets correctly partial. | Whole requested proof inventory and cumulative traversal limits untested. |
| 28 | Withheld field/disabled observation honest; no diagnosis output. | Advisory recording, future reuse and remote-trace diagnosis absent/unrun. |
| 29 | Not run. | Target non-reading frontier branch absent. |

## Why the historical replay failed

The retained twelve-case source SHA is `9d11594782abfb417d0f3a826bfb1f91f3a523ac`, but the available generation uses mapper 3. A Git SHA alone does not reproduce an indexed representation. RQE-01 rejects the missing canonical parent mapping as `unsupported`; RQE-03 cannot establish the expected full dependency result; RQE-04 lacks declared-reference disclosure; RQE-05 cannot establish mapping fitness and returns `unknown`, not build permission. Original expected assertions were retained, so these eight mismatches remain visible. RQE-02-P/N and RQE-06-P/N passed their bounded assertions.

The reproducibility gap is concrete: evaluations must pin or check **generation ID, mapper/contract version and required mappings**, alongside source SHA and code fingerprint. Do not reinterpret failed prerequisites as successful negatives or compare them as answer-quality regressions against the current mapper-7 graph.

## Next work, in priority order

1. Investigate the live routing gate: both explicitly typed research requests asked the user to choose an ability before any retrieval. Reproduce with the saved requests and inspect prompt/context/policy together; do not treat confidence as answer correctness.
2. Make exact-ID retrieval reachable through the question planner's offered contracts, then test a valid offered choice with the original RS-03 question. The invalid-selection guard should remain intact.
3. Replace technical/repeated clarification wording with a focused intent choice; exercise an actual answer and resume. Preserve caller authority over population.
4. Make evaluation prerequisites explicit so a retained old projection cannot masquerade as a reproducible baseline.
5. If separately authorized for implementation, build the missing target orchestration: method portfolio/frontier navigation, bounded return loops, shared comparison and advisory memory. Their design scenarios are not current functionality.
6. After a separately scoped repair, repeat bounded original-question tests and exercise actual human resume. The current two live canaries are complete; no further provider calls were made or silently authorized by this report.

No incorrect numeric or quoted-source answer was found in the reviewed fresh graph facets. That narrow finding is not a claim of general answer quality, real-Jev performance, or completion of the proposed journey.
