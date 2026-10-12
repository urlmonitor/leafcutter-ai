---
title: 12. Missing-query authoring, admission and durable reuse
description: Historical analysis and saved observations for 12. Missing-query authoring,
  admission and durable reuse.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-05'
components:
- knowledge_management
- decision_kernel
---
# 12. Missing-query authoring, admission and durable reuse

Analysis only; inspected HEAD `887c66d3896ba7727ce41b743887210a3883c6ce`. No production/AC changes, test executions, provider calls or database writes. This addresses S8 and RS-23/24; it does not design the generic method loop or optional input-generation service.

**Recommendation:** complete the existing bounded authoring path, its delivery contract and compatibility lifecycle. It already produces real parameterized Neo4j Cypher. Arbitrary submitted Cypher is unnecessary for the demonstrated component-to-AC-to-test need. Genuine coding-agent delivery and complete lifecycle proof remain open.

## Evidence and concrete gaps

The [older gap analysis](../2026-10-02-retrieval-completion-gap-analysis.md) correctly calls S8 partial. Fresh [graph receipts](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/results.md), [default receipts](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/default-source/results.md) and [aggregate](../../../reports/retrieval-scenarios-2026-10-02-retest-887c66d3/aggregate.json) do not execute query build: graph starts stop at population clarification; default starts stop at synthesis handoff. They add no actual-author or lifecycle evidence.

Verified repository anchors below use one-based lines:

| Anchor | What exists; limit |
|---|---|
| `knowledge/capability_fit.py:11`; `integrations/query_graph.py:106`; `integrations/query_growth.py:266` | Source kinds/fields/relationships, catalog completeness and one-build-attempt guards. The integration reads `required_relationships` with an empty default, but no producer populates it in these integrations. Manifest support alone cannot establish whether a particular canonical fact exists. |
| `integrations/query_planning.py:101`; `kernel/contracts/query.py:5` | Build packet carries question, repository/SHA/generation, components, need/attempt, catalog, budget and generic expected-result text. It has no explicit resolved scalar arguments, answer requirements, original-versus-effective question, or prior partial-evidence references. Continuation retains more context than the coding contract transmits. |
| `kernel/capabilities/host/query_build.py:9` | Registered `host.query_build`/`build_query` authors candidate data; no activation authority. Generic transport registration proves a handoff boundary, not an actual agent invocation. |
| `knowledge/query_models.py:63`; `knowledge/query_compile.py:53`; `knowledge/query_execution.py:34` | Required typed seed, at most two allowed directed edges, parameterized filters, bounded scoped reads and truncation. The compiler creates actual Cypher. Unsupported vocabulary needs ordinary code/contract work. |
| `knowledge/query_admission.py:70,149,205` | Trusted verifier recompiles and executes declared positive/empty cases plus invalid-input, injection and foreign-scope checks. Its receipt explicitly says `semantic_usefulness_proven=False`; expectations and reviewer attribution come from the author, not independent semantic approval. |
| `knowledge/query_store.py:31,88`; `knowledge/query_catalog.py:34,59` | Integrity-checked files, exclusive activation lock, atomic replacement, compare-and-swap and retained digests. No retirement/rollback/recovery policy. Identical-digest activation returns the old entry, so fresh verification can appear in the receipt without appending its new-source history to durable storage. |
| `knowledge/query_execution.py:88` | Runtime mapping check checks kinds, not a full mapper/compiler/field/relationship compatibility fingerprint. Active descriptors are not source-compatibility filtered. |
| `integrations/query_growth.py:186`; `integrations/query_graph.py:190` | Resume matches candidate/query digests, source, generation and operation/version; execution bypasses reselection. Graph execution ends locally, rather than returning a common method attempt to comparison. |
| `kernel/scheduler/guards.py:157`; `kernel/scheduler/merge.py:165` | Existing per-run full-payload dedup links identical requests. Different need IDs or budgets change identity; this is not concurrent same-build coalescing across runs. The question-plus-SHA attempt label is not such a coordinator. |

“No endpoint” must therefore resolve to a classified outcome, not automatically to coding:

- Missing required input: bind/discover/clarify through the input owner.
- Canonical fact absent: explicit source-fact gap; no query can invent it.
- Fact present but unprojected/undisclosed: mapping/disclosure gap with attributable diagnostics.
- No diagnostics, outage, stale source, denial or incomplete catalog: unknown/unavailable, not missing query.
- Supported data but unsupported output/operator contract: ordinary governed contract/code change; do not force it into the recipe.
- Supported, expressible data/path with no compatible offered operation or sufficient alternative: eligible query gap.

RS-23's fact-versus-mapping distinction still needs the attributable source comparison. A valid empty result alone proves neither cause.

## Options

| Option | Tradeoff |
|---|---|
| **A. Finish bounded recipe authoring and lifecycle (recommended).** | Smallest change; reuses actual Cypher compiler, ports and durable kernel. Clearly report needs outside the grammar. |
| B. Coder delivers reviewed registered-query source changes through ordinary software delivery. | Appropriate for new operators/contracts; broader expressive range, but slower and dependent on independent tests/release before availability. Keep it separate from immediate catalog admission. |
| C. Accept constrained free-form Cypher dynamically. | More flexibility, much larger parser, authorization, resource-bound and compatibility surface. Existing proofs do not cover it; defer absent a demonstrated need. |

KM-500b-4 explicitly records the tension between the original guide's rejection of an invented graph language and the later bounded recipe design. Record a narrow architecture decision approving the authoring boundary before claiming guide-compliant readiness; fixture success cannot resolve that decision.

## Smallest implementation sequence and ownership

1. **Qualify the gap in existing LangGraph nodes.** System owns source/contract diagnostics and eligible offers; Jev owns the bounded semantic choice of no matching operation. Require explicit relation/field needs and preserve unknown causes. Recheck the catalog immediately before creating work. Missing inputs remain with the preparation/clarification owner.
2. **Complete the typed build packet and deduplicate.** System owns one durable build identity scoped to authorized catalog/repository, source/generation/mapper, normalized requirements and relevant input contract. Retain individual waiting-need identities separately. Reuse the scheduler for within-run linking; if cross-run reuse of active builds is required, add a narrow durable claim/waiter mechanism through the existing catalog/host ports, not another scheduler. Different permissions or source contracts cannot share authority.
3. **Deliver through the existing host boundary.** Coding host alone authors descriptor/cases. Bind actual actor/delivery identity, interaction revision and candidate digest to the issued build request. Preserve budgets and accessible evidence. Record inability explicitly. The actor receives no catalog-write authority.
4. **Independently evaluate and activate.** Validator owns compilation, safe read verification and separately reviewed semantic expectations for the original need; System's dedicated activation capability owns permissioned atomic persistence. Preserve descriptor, compiled digest, source/mapper identity, test results and independent evaluation provenance. Failure retains the prior active catalog and unresolved need.
5. **Resume once and return an attempt.** System consumes only the current matching receipt, runs the admitted digest and attaches evidence/limits to the original need. Kernel checkpoint/interaction machinery owns restart and replay. Jev's existing assessment owner judges sufficiency; query growth must not become a second comparison loop.
6. **Finish compatibility lifecycle.** Neutral catalog/admission owner defines source-data drift versus mapping/contract incompatibility, fresh reviewed expectations, retained-reader policy, retirement, verified rollback and interrupted-writer recovery. Persist revalidation history even when query digest is unchanged. Lifecycle mutations use the same narrow authority and atomic concurrency boundary.

**Interface to other slices:** accept original question, effective question, need ID, typed answer obligations, resolved arguments with provenance, authorized scope/source pins, prior attempt/evidence references and remaining shared limits. Return one attempt ID with query/version/digest, actual arguments/source identity, evidence/coverage/limitations, measured consumption and explicit success/partial/failed/denied/unsupported outcome. Input generation may propose values but cannot fabricate source facts or authorize build. The method loop decides alternatives/comparison; this slice supplies an attributable attempt and never resets budget or erases earlier useful evidence.

## AC status and precise completion boundary

In `docs/acceptance-criteria/knowledge-management/KM-500-research-capability-growth/`: KM-500a-3, b-1, b-2, b-3 and c-1 are approved/`done`; preserve their bounded evidence. KM-500e-4 is approved/`in_progress`: complete factual-gap discrimination and real relationship/field contract propagation. KM-500b-4 and b-5 are approved/`todo`, with empty coverage/implementation lists: actual author/public transport/fresh-process reuse and complete compatibility/lifecycle remain obligations. RS-23/24 remain partial.

Reconcile concurrent equivalent-build sharing and shared-method-attempt return against the existing b-1/c-1/c-3 contracts; do not mark them covered merely because generic dedup or continuation exists. No AC mutation is performed here.

## Tests and evidence required

Existing tests are reusable, not new execution claims:

- `tests/knowledge_live/query_growth_local_checks.py:103,143,188` uses real Git/projection/Neo4j, verifier, catalog and checkpoints, but loads a prewritten candidate and scripts Jev/human/synthesis. Reopens objects and starts a new run in the same process.
- `tests/knowledge/test_query_admission.py:228` actually spawns CLI catalog discovery; it does not execute a newly authored query in that process. Lines 189/266 cover fresh receipts, retained digests and simulated failed replacement, not crash recovery or lifecycle completion.
- `tests/knowledge/test_query_growth_kernel.py:212,221` covers controlled resume/reuse and denied activation; `test_query_growth_adversarial.py:18,126,150,167` checks mismatched receipt, bounded stopping, failed delivery and source-kind eligibility.

Independent test-writer should establish meaningful RED cases before coding, following `CLAUDE.md:263,333`, coder red-baseline rules, test-writer real-artifact/discrimination rules and ITPO integration-contract guidance; no planning workflow is invoked here.

Required discriminating proofs:

1. Public packet round-trip preserves scalar inputs, exact obligations and prior partial context. Three RS-23 source variants plus missing-input/unsupported-contract/unknown/outage controls dispatch build only for the real query gap.
2. Two equivalent concurrent needs produce one authoring job, each resumes once; different source/permission requirements remain distinct. Duplicate/stale submissions and process restart cannot execute twice.
3. Actual authorized coding actor produces a new candidate for the issued request; capture actor, input/output hashes and revisions. Independent source-derived/held-out expectations catch an unrelated but mechanically passing recipe. Missing actor/provider prerequisites mean `not_run`.
4. Fresh OS process discovers **and executes** the admitted digest without rebuilding; original need/source/partial context survives. Unsafe input is rejected before DB work; denied activation causes zero verification/serving calls and no fallback bypass. A semantically rejected candidate may have undergone bounded verification reads, but must never execute as admitted retrieval.
5. Real catalog crash/reopen and concurrent activate/retire/rollback retain consistent history. Two source generations include legitimate changed IDs and incompatible mapping; stale comparison, missing retained generation and permission denial remain explicit. Verify unchanged-digest revalidation history survives restart.

The local Neo4j proof writes its isolated fixture namespace; it was inspected, not rerun under this read-only analysis boundary.
