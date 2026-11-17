---
title: Retrieval scenario evaluation after origin sync
description: Independent before-and-after review of the same retrieval scenarios on merged code 84006ac3.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# Retrieval evaluation after syncing origin

**The updated code did not unblock either of the two observed question-to-answer paths.** Both real-Jev starts again asked the user to choose an ability before any retrieval. The eight direct graph probes still returned the expected facts or honest limitations. The historical evaluation remains 4/12 because it uses an older projection, not because eight new incorrect answers appeared.

This is a fresh execution on HEAD `84006ac3ff35d834949d6e65ded80e82e950f99b`, including origin/main `d50c0dc48a0feecbbfbba87400e024c87dd3f245`. It compares with the [earlier independent report](2026-10-02-retrieval-scenario-results.md); it does not overwrite that report or infer outcomes from the merge. Execution-code fingerprints are saved with each run because local modifications also exist.

## Before and after

| Lane | Before sync | Fresh post-sync observation | Independent assessment |
|---|---|---|---|
| Eight active graph probes | Correct bounded facts/refusals | Same eight answer objects and evidence arrays | No factual regression observed in these facets. |
| Twelve historical controls | 4 passed / 8 failed | 4 passed / 8 failed | Same older-projection prerequisite mismatch; not eight current-graph wrong answers. |
| RS-02 real Jev | Research probability .67; confidence .51; ability-choice wait | Research probability .67; confidence .50; same wait | No focused population clarification or retrieval reached. |
| RS-03 real Jev | Research probability .58; confidence .36; ability-choice wait | Research probability .59; confidence .39; same wait | Known-ID question unanswered; graph was never queried in this live run. |
| Controlled RS-02 | Technical/repeated scope clarification | Same prompt, including “population, population” | Honest no-count wait; presentation defect unchanged. Human resume not tested. |
| Controlled RS-03 invalid selection | Script chose unoffered get_entities; correctly rejected | Same invalid_request rejection | Negative control, not a supported-query failure. |
| Controlled RS-03 allowed choice | Script chose offered clarify; component-ID question | Same component-ID question | Allowed transition works; forced choice is not autonomous model-quality proof. |

The two authorized live requests made **one actual provider call each: 2 of the maximum 24**, resolved model `jev-1.13.0` from configured `jev-latest`. No retries, fabricated human answers, resumes, graph writes, embeddings or remote Langfuse export occurred. Both traces record `routing.assessed` with `insufficient_context` and `low_confidence`. The provider returned successfully and selected `research`; the system's routing policy chose to ask the human instead. These two observations do not establish the correct calibration/prompt/policy repair or a causal regression from the merge.

The actual RS-03 response again said:

> I am not sure how to handle this request: "For KM-500c-2, what must tests demonstrate?". Which of these fits best? You can also say it in your own words.

Its output was null, evidence IDs empty, and the only capability choice was `research`. RS-02 got the analogous ability question, not a question about which AC population “test writing” means. No answer was fabricated, but neither live scenario achieved its intended behavior.

## Fresh factual checks

The serving source/generation did not change: source `59269e024e4d0290b68b03d0d382745966e67e29`, generation `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`, mapper 7, semantic readiness false. The [independent archived-source oracle](2026-10-02-retrieval-active-source-oracle.json) therefore remains applicable. The merge updated execution code; it did not publish a new graph.

I independently checked the new output, not just the executor's verdict:

- Root-excluded TQ-500f L2/L3 enumeration returned **15 ACs: 5 done, 10 todo**. Every ID, work status and source-file hash matched the oracle; the new answer and evidence objects also exactly match the prior run. This is not the 11 terminal-leaf population or all repository test-writing requirements.
- The five incoming declared dependencies matched the independent set. A four-result control stayed partial with `exact_total=null`.
- Exact KM-500c-2 criteria matched SHA-256 `9cfea912e97757a50beaab42e39ccfd82dd6f2bbf0d6e9425daf3e1d9e2617d3`, with `/criteria` attribution at the correct source. The text explicitly separates successful build, query execution and answer assessment.
- Withheld work_status returned partial and null status counts; clipped clauses stayed partial. An injected outage remained unavailable/unresolved. No oracle value was inserted into actual output.
- The observation probe still has disabled observation and no diagnostic assessment. It is not proof of a verified trace, incident cause or learned strategy.

These use the actual public KnowledgeService/Aura route with explicit typed requests and named boundary controls, not natural-language method selection. The natural query catalog still omits the direct `get_entities` operation: the recorded controlled selection menu confirms this after sync. The script selecting that unoffered operation is correctly rejected; its failure cannot be called a failed valid query.

The historical twelve-case lane still uses retained source `9d11594782abfb417d0f3a826bfb1f91f3a523ac`, mapper 3. Missing parent mapping, declared fields and capability metadata explain the unchanged assertion failures. Source SHA alone is insufficient to reproduce projection prerequisites: generation, mapper and contract readiness must also match.

## All 29 dispositions

Denominators are separate: **2/29 original-question scenarios received fresh real-Jev starts; both stopped before retrieval. The other 27 were not executed as complete target journeys. Zero full target-flow passes were demonstrated.** Eight fresh typed-service probes cover narrower facets of ten scenario IDs; three controlled kernel starts cover RS-02/03. The twelve historical assertions are another lane and are not added to the RS pass count.

The following retains all 29 cases. Rows for absent target capabilities use the [independent feasibility map](2026-10-02-retrieval-scenario-execution-map.md); incoming changes affect claim retention/caps and host integration, not the missing traversal, multi-method comparison or advisory strategy orchestration. “Not run” is not a simulated failure or success.

| RS | Fresh observed answer or facet outcome | Complete target-path limitation |
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

## Evidence and next priorities

The dated [execution index](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/execution.json) links all cases. Raw receipts: [active eight](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/active-controls.json), [historical twelve](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/historical-controls.json), [controlled kernel](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/kernel-controls.json), [allowed-choice control](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/kernel-valid-controls.json), [RS-02 live](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/RS-02.live-response.json), [RS-03 live](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/RS-03.live-response.json), [effective config](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/effective-config.json), [replay wrapper](../../reports/retrieval-scenarios-2026-10-02-post-sync-84006ac3/replay.py).

The wrapper redirects the unchanged retained runner into a new report directory and separate checkpoint/catalog paths. The effective merged config includes max_claim_needs=25. Existing receipts remain historical evidence, not rewritten results.

Next repair priorities remain: investigate why explicit research requests require an ability choice; expose valid exact-ID retrieval to planner selection; improve focused clarification; pin projection prerequisites in evaluation. The proposed traversal/portfolio/advisory loop still needs separately scoped implementation. This evaluation changed no runtime or acceptance-criterion statuses and did not repeat broad unit suites.
