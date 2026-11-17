# Retrieval retest on merged code 887c66d3
**Later default-source comparison:** The same two questions were also run with the actual default source policy on isolated887c66d3 bytes. Both reached native evidence and a host synthesis wait, using10more calls; aggregate18/24. See [the separate default-source report](default-source/results.md) and [aggregate totals](aggregate.json). The graph-only observations below remain unchanged.

The initial routing repair works for these two typed research requests. Both original questions now enter research and repository retrieval, but neither reaches a graph query or returns an answer. Both stop at a technical population clarification. This is progress beyond the previous ability-selection wait, not successful end-to-end retrieval.

## Fresh live outcomes

| Original question | Actual result | Real Jev calls | Elapsed |
|---|---|---:|---:|
| RS-02: How many ACs concern test writing? Exclude parent requirements. | Research entered; asks for population/root clarification; no count or evidence. | 3 | 1.661 s |
| RS-03: For KM-500c-2, what must tests demonstrate? | Literal ID recognized, but an irrelevant count-population clarification blocks the exact-ID question; no criterion or evidence. | 5 | 2.267 s |

Both responses are `waiting_human`. Their prompt begins: “Please supply the missing population choices: population, population.” It then asks for JSON with `scope` and technical values such as `root_excluded` or `returned_entities`. The complete returned prompts, original requests and local traces are retained in [RS-02](RS-02.live-response.json) and [RS-03](RS-03.live-response.json).

RS-02 genuinely needs a precise definition of its population; this run does not establish that asking any clarification is wrong. The demonstrated problem is the duplicated technical wording and the lack of a focused ordinary-language question. RS-03 is already an exact-ID request: Jev recognizes `KM-500c-2`, yet the population gate stops it before query selection. That observed stop is distinct from the separate catalog/input-binding gap exposed by controlled inspection.

TypeSafe resolved `jev-latest` to `jev-1.13.0`. The two authorized starts consumed 8 of 24 allowed calls, 10,197 input tokens and 1,782 output tokens; recorded estimated cost was $0.000428274. There were no human/host resumes, fabricated answers or extra live attempts. No hard provider token cap is exposed by this configuration; call, input-size and time limits are recorded in [the consent and execution boundary](live-boundary.json).

## What changed from the previous test

At code `84006ac3`, each question stopped after one live call at initial capability routing. At `887c66d3`, the validated typed research request is bound to research, while Jev still performs research planning and answer-contract decisions. The runs now reach the next unresolved step. This tests the retained public typed research entry with the original question; it does not prove an untyped/default-source caller path.

| Evaluation lane | Fresh result | What this proves |
|---|---|---|
| Two original questions, real Jev | 0 answers; 2 waits after research entry | Initial typed routing progressed; the answer-scope step remains blocking. |
| Eight active typed graph controls | 8 correct against the independent source oracle | Count/field/criterion/dependency and honest partial/outage behavior at the direct service boundary. |
| Pagination and terminal-leaf controls | Both saved-result checks correct | Three partial pages remain partial; 11 terminal leaves are distinct from 15 root-excluded descendants. |
| Twelve historical retained controls | 4 passed, 8 failed | Older mapper-3 projection lacks expected prerequisites; these are not eight newly observed wrong answers. |
| Three scripted kernel starts | Population wait, rejected invalid choice, allowed clarification | Control behavior only; scripted decisions do not establish semantic quality. |

The eight active answer/evidence objects equal the previous run and match the independently pinned oracle. The full target scenario denominator remains **2 of 29 live starts, 27 not run as full journeys, 0 full target passes demonstrated**. Lower-layer facets do not promote an entire scenario to passed.

## Direct evidence and limits

The direct population query returns exactly 15 TQ-500f descendants excluding only the root, with 5 `done` and 10 `todo`. The separately requested terminal-leaf population returns exactly 11, with 4 `done` and 7 `todo`. The dependency query returns the five canonical one-hop incoming `depends_on` records. Exact criterion text and `/criteria` attribution match immutable source; work status attribution points to `/work_status`.

Withheld work statuses remain unavailable rather than being inferred from lifecycle status. Clipped criteria and four-result subsets remain partial with no exact total. The injected outage is unresolved with unknown source and no evidence. The disabled-observation control does not establish incident diagnosis or a verified Langfuse trace. See [active outputs](active-controls.json), [independent grades](execution.json) and [the immutable source oracle](../../docs/analysis/2026-10-02-retrieval-active-source-oracle.json).

Three real service continuation pages contain 5 + 5 + 5 distinct records. Every page, including the last with no continuation, reports partial and no global exact total. The saved [page receipts](continuation-controls.json) and [leaf receipt](leaf-control.json) are valid. After saving them, the helper exited 1 because its console summary attempted to JSON-serialize an `AnswerAssessment` object. [The error log](continuation-checks.log) is retained. Offline grading verified the saved receipts; no query was rerun and this helper execution is not represented as a clean process pass.

The scripted exact-ID probe selected `get_entities` when that option was not offered. The actual response correctly rejects the unoffered choice. Its separately retained, permitted `clarify` probe asks for a component ID. Neither is a successful autonomous exact-ID answer. See [scripted starts](kernel-controls.json) and [allowed clarification](kernel-valid-controls.json).

## Code, data and configuration identity

- Evaluated code: `887c66d3896ba7727ce41b743887210a3883c6ce`.
- Actual hosted source: `59269e024e4d0290b68b03d0d382745966e67e29`, mapper 7.
- Active generation: `20c370b99a39e0939e985846c9132986f8dc3052007b0dec5b43c19ddda7c28f`; semantic readiness is false.
- Historical controls use source `9d11594782abfb417d0f3a826bfb1f91f3a523ac` and mapper 3.

Readiness and oracle/source identity were checked afresh. The graph was not republished to the new code revision. All pinned runtime source hashes remained unchanged, and all 35 prior receipt fingerprints still match. Fresh analyst documents were not ingested: this retained canary configures only `knowledge.graph`, and both actual enrichment traces show zero files scanned and no consulted sources. Source resolution for direct graph evidence is pinned to immutable Git bytes.

This is the **same graph-only canary configuration**, not the default all-source configuration. The default repo-text sources differ, so incoming context enrichment was unavailable in these runs. [The source-policy comparison](source-policy-comparison.json) separates that harness limitation from observed product behavior. A separately scoped default-source test would be needed to assess that route; none was added here.

No graph writes, indexing, query activation, embeddings or remote Langfuse export occurred. Live calls transmitted the questions, research-need descriptions and bounded answer-contract choices/metadata, but no retrieved repository excerpts. The local tracer records outbound-state fingerprints rather than full outbound provider payloads; transmission categories are identified from the saved calls and pinned producer code.

## All 29 scenario dispositions

“Facet correct” means only the named lower-layer behavior was checked. “Not run” is not a claim of failure or implementation absence. Target gaps and original catalog fixtures remain separately recorded in [the execution index](execution.json).

| Scenario | Target journey in this retest | Observed result or bounded facet |
|---|---|---|
| RS-01 - Caller asks for an answer, not an operation | Not run | Not run in this retest. |
| RS-02 - Ambiguous population gets a focused clarification | Live start; incomplete | Live reaches research and answer-contract planning, then technical population clarification; no count or evidence. |
| RS-03 - Known exact ID can take a simple route | Live start; incomplete | Live reaches research and recognizes KM-500c-2, but population gating asks a count-scope question; no exact-ID query or answer. |
| RS-04 - Relevant advice cannot choose for Jev or widen access | Not run | Not run in this retest. |
| RS-05 - The catalog contract must fit the answer requirement | Not run | Count/field facet correct in active RQE-01-P. |
| RS-06 - Missing query input is discovered or clarified | Not run | Not run in this retest. |
| RS-07 - Caller keywords suffice without model generation | Not run | Not run in this retest. |
| RS-08 - Optional term generation is bound and checked | Not run | Not run in this retest. |
| RS-09 - Multiple searches stay separate until shared comparison | Not run | Not run in this retest. |
| RS-10 - Failed search preserves a useful sibling result | Not run | Not run in this retest. |
| RS-11 - Follow declared graph edges with direction and scope | Not run | Five direct declared dependents correct. |
| RS-12 - Follow repository folders and files without inventing dependencies | Not run | Not run in this retest. |
| RS-13 - Cyclic frontier does not repeat completed reads | Not run | Not run in this retest. |
| RS-14 - Escaped or stale path is refused without losing history | Not run | Not run in this retest. |
| RS-15 - Partial navigation cannot prove absence or exact totals | Not run | Partial-page facet correct; no exact total. |
| RS-16 - Switch method after a bounded dead end | Not run | Not run in this retest. |
| RS-17 - Compare observed attempts against the same question | Not run | Not run in this retest. |
| RS-18 - Deduplicate records while keeping every provenance path | Not run | Not run in this retest. |
| RS-19 - Successful execution with missing requested field stays unresolved | Not run | Missing work-status facet correct; counts withheld. |
| RS-20 - Complete enumeration and source-backed exact count | Not run | Exact active-source 15/5/10 facet correct. |
| RS-21 - Answer wording must preserve limits and citations | Not run | Not run in this retest. |
| RS-22 - Structured facts can bypass extra wording | Not run | Direct structured criterion/locator facet correct. |
| RS-23 - Missing source fact, field mapping and query are different | Not run | Not run in this retest. |
| RS-24 - Query build is governed and resumes once | Not run | Not run in this retest. |
| RS-25 - One failure is not global failure; no useful route stops honestly | Not run | Deliberate outage correctly unresolved. |
| RS-26 - Focused clarification after evidence preserves findings | Not run | Not run in this retest. |
| RS-27 - Budget exhaustion yields an attributable partial answer | Not run | Clipped criterion/four-result facets correctly partial. |
| RS-28 - Advisory learning records observation, not truth or approval | Not run | Withheld field/disabled observation honest; no diagnosis output. |
| RS-29 - Non-reading traversal decision bypasses read and post-read judgment | Not run | Not run in this retest. |

## Reproduction record

[The retained wrapper](replay.py) invokes the existing public evaluation helper with a new output directory and isolated checkpoint/catalog paths. [The recipe](rerun-recipe.json) lists the commands and closed live-call boundary. [The offline finalizer](finalize.py) grades saved output against immutable source without contacting Aura or a model. The pagination helper's final print error remains recorded separately above.
