# Default-source retest: repository evidence reaches a host synthesis handoff

On the same merged code, both original questions use the default native source policy successfully enough to produce cited evidence and request `synthesize_evidence`. Both return `waiting_host`; neither returns a final answer because this evaluation stops at the first wait and does not supply a host response. This is a legitimate public handoff, not the graph-only population-clarification stop.

| Original question | Returned state | Evidence IDs offered to host | Real Jev calls | Elapsed |
|---|---|---:|---:|---:|
| RS-02: How many ACs concern test writing? Exclude parent requirements. | waiting_host / synthesize_evidence | 6 | 5 | 10.008 s |
| RS-03: For KM-500c-2, what must tests demonstrate? | waiting_host / synthesize_evidence | 8 | 5 | 3.568 s |

The actual model was `jev-1.13.0`. Each run performs research planning, three native relevance reranking calls and research assessment. Context enrichment scans 180 files and retains six bounded context items per question. `host_operations=1` per response records creating the handoff; no external host model was invoked.

The two new runs consumed 10 calls, bringing the complete fresh retest to **18 of 24 authorized Jev calls**: four starts across the same two scenarios. There were no retries or resumes. **Zero final answers and zero full target passes are demonstrated; 27 other full scenario journeys remain unrun.**

## Evidence quality and configuration limits

The default configuration has 15 sources and `knowledge.backend=none`. It uses repository text and local knowledge maps, with host handoffs where configured. No graph source or Aura endpoint was added. These outcomes therefore cannot prove Neo4j behavior. [Exact resolved configuration](effective-config.json) and [the complete receipt index](execution.json) retain the settings and actual source IDs.

Both requests preserve their original natural question and typed research contract, with no hidden operation, selected AC ID or population. Their trusted read scope remains `docs`. Code and native source bytes are pinned to `887c66d3896ba7727ce41b743887210a3883c6ce`, independently materialized from Git into an isolated temporary source directory. All 10,498 archived file hashes remained unchanged; new analysis and retest files were not present. [The source manifest](source-pin.json) records the archive and file hashes.

The native evidence is not yet a correct answer. RS-02's packet includes two AC-store records, build-dataflow sections and the prior question catalog; it supplies no complete population enumeration. RS-03's packet includes testing guidance and already committed evaluation/oracle/catalog documents, but does not cite the canonical `KM-500c-2.yaml` itself. Existing evaluation material is an actual default `repo.analysis` source; its appearance must not be mistaken for independent answer-quality proof. The full citation list with source-file hashes is in [execution.json](execution.json).

Our explicit local telemetry safety override was `telemetry_excerpts=none`. The resulting persisted host input artifacts contain `[OMITTED:excerpt]`, although they retain evidence IDs and locators. This is an observed limitation of this bounded evaluation configuration, not proof that the unchanged default telemetry setting has the same effect. We did not reconstruct, replace or submit the host inputs. Exact saved artifacts are [RS-02 host input](RS-02.host-input.json) and [RS-03 host input](RS-03.host-input.json).

The [raw RS-02 response/trace](RS-02.live-response.json) and [raw RS-03 response/trace](RS-03.live-response.json) are authoritative. Both executions exited 0. No paid synthesis, graph writes, indexing, query activation, embeddings or remote Langfuse export occurred. The new lane preserves all graph-only receipts and all 35 earlier receipt fingerprints.

## Relationship to the graph-only lane

The earlier graph-only starts still correctly show both questions stopping at answer-population clarification before a graph query. This default-source lane shows a different route: native search, evidence assessment, then host synthesis. Neither route produced a final answer in this bounded test. The initial graph-only boundary summary's copied old prompt text was corrected from its actual fresh response; raw responses and historical receipts were preserved.

The [aggregate index](../aggregate.json) keeps lane totals separate. The [retained runner](replay_default.py) has one-shot guards; it must not be run again under this completed scope.
