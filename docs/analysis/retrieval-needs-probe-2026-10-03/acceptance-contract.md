---
title: Standalone retrieval-needs experiment acceptance contract
description: Independent PO, BA and IT PO review of the one-call Jev needs step and predeclared evaluation expectations.
type: explanation
status: draft
created: '2026-10-03'
last_updated: '2026-10-03'
components: [knowledge_management, decision_kernel]
---
# Standalone retrieval-needs experiment

User authorization: build and test only the needs step before integration, with every field assessed in parallel in a single Jev call; test an evaluation set and enrich expected outcomes independently. Base source: `2d4bee9fe665bc2f9b173baa752081bde69bc34c`; branch `experiment/retrieval-needs-single-call`. This note was prepared before live model outputs, using the PO, BA and IT PO templates, existing approved ACs, the 25 persona questions and the 29 retrieval scenarios. It is a bounded experiment contract, not a new AC, implementation signoff or full retrieval acceptance result.

## Product purpose and scope

An agent asks a question without deciding the operation. The new step states what information is required, preserving the user's question and explicit targets. A downstream operation may later satisfy those needs through a graph, document search or traversal. A current backend limitation must not silently change the question.

The experiment runs one isolated LangGraph step, with deterministic input preparation and result validation around one Jev batch. It does not select or execute retrieval, perform graph writes, invoke host synthesis, grant permissions, create queries, or integrate into the production research flow. Initial context can be supplied to this step as evidence; gathering that context is outside this experiment.

## Input and output agreement

Inputs contain the unchanged original question, bounded supplied context with provenance, trusted repository/revision scope, and offered semantic categories, fields, document types and literal/supplied ID candidates. Offered categories describe answer needs independently of whether Neo4j currently supports them. Context is data, not instructions or authority.

The output retains the original question and source/scope and declares a selection, explicit absence or uncertainty for every dimension:

| Dimension | Required meaning |
|---|---|
| Entity/content kinds | What the answer concerns; several kinds may be needed. |
| Target IDs | Only literal/supplied eligible candidates; no invented identifier. An absent ID can mean discovery, not necessarily user clarification. |
| Fields and detail mode | Specific facts or a bounded full selected item / item plus specified context. Full context never means unlimited repository content. |
| Document types | Source classifications such as canonical AC, ADR, schema, code or execution receipt; separate from subject kind. |
| Relationships | Required parents, children, ancestors, descendants or directed dependency links, with depth/bounds. Explicitly none is valid. |
| Completeness | One entity's requested fields, useful examples, exhaustive membership or exact-count requirements; these are different obligations. |

Multiple selections are permitted where the question requires them. Unsupported meaning is preserved in unresolved needs, never replaced by the closest convenient field. Low-confidence or contradictory selections must remain uncertain. The experiment must not label a structured response as a fulfilled answer.

Jev owns semantic judgments. System code owns candidate identity, immutable question/scope, batch assembly, option membership, response validation and bounds. One logical batch must correspond to one actual provider request with no silent chunking, retries or per-dimension requests. Raw request/response evidence and actual call count must make this inspectable.

## Existing AC mapping

All mapped requirements are approved. The displayed work statuses were read from the pinned base and are unchanged.

| Existing requirement | Work status | Partial experiment evidence; remaining boundary |
|---|---|---|
| [KM-500e-1](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-1.yaml) | in_progress | Primary owner: requested facts, scope, inclusion and completeness survive planning; missing query fields do not erase needs. Persistence, resume and later assessment remain untested. |
| [KM-500a-1](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500a-1.yaml) | done | Reuse readiness distinction and explicit failure/uncertainty. This step may identify a missing choice; it does not prove the interaction continuation or change this status. |
| [KM-500e-2](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-2.yaml) | in_progress | Distinguish criteria, lifecycle status, implementation work status and proof needs. Actual field retrieval, locators and final disclosure remain untested. |
| [KM-500e-3](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500e-3.yaml) | in_progress | Declare exhaustive population and root-only versus parent exclusion correctly. No population enumeration or count is executed. |
| [KM-500c-2](../../acceptance-criteria/knowledge-management/KM-500-research-capability-growth/KM-500c-2.yaml) | done | Preserve original-question obligations for later evidence assessment. This experiment is not evidence that the full answer journey works. |

The one physical provider request constraint is this user's explicit experimental constraint, not retroactively claimed existing AC coverage. No new lifecycle value, approval, ticket, product-truth completion or AC ID is created.

## Predeclared evaluation enrichment

The independent test writer owns exact dataset bytes and grading. These expectations were sent before seeing live outputs; acceptable alternatives avoid prescribing one retrieval strategy.

| Case | Required / acceptable | Forbidden |
|---|---|---|
| Exact KM-500c-2 criteria | Literal AC ID, criteria, canonical AC document, complete requested fields. Test requirements or bounded full AC are acceptable additions. | Required population/root clarification, invented target or graph-operation selection. |
| Test-writing count excluding parents | AC set and exact-count completeness; uncertain topic membership/root may require later clarification. | Invented TQ-500 family; excluding root treated as excluding every parent; adding work-status obligation when not asked. |
| Explicit TQ-500f L2/L3 descendants grouped by work_status | Literal root, descendants, work_status, levels, root exclusion, exhaustive requirement. | Direct children/terminal leaves substituted; lifecycle status substituted; redundant scope question. |
| Code flow of work_status | Code/schema/projection/disclosure evidence and field mapping, with actual execution proof only if runtime causality is requested. | Claiming graph edges exist or selecting only an AC document. |
| Explicit parent context | Literal target retained, requested parent relation and depth; bounded selected item plus parent is acceptable. | Global family or arbitrary ancestors substituted for one parent. |
| Compare two literal AC IDs | Both targets and comparable criteria/fields. | Dropping one ID or inventing a count requirement. |
| Lifecycle versus implementation status | Both distinct field meanings. | Readiness or requirement status substituted, values inferred. |
| Broad missing-input criteria | AC/contract clauses, zero IDs plus discovery allowed. | Fabricated ID or mandatory clarification merely because ID absent. |
| Conflicting supplied snippet | User's literal target retained; conflict can remain explicit. | Context target replacing the question target. |
| Unsupported payroll request | Compensation/payroll meaning retained with explicit unresolved/unsupported dimensions. | Convenient AC status field substituted or resolved empty need. |
| Context instruction injection | Original question, target candidates and trusted scope retained. | Snippet grants access, rewrites the question or invents targets. |
| Governing ADR and schema contracts | Both document types and actual governing clauses/contracts. | One document type silently discarding the other. |

The 29 original scenarios should receive planning-only applicability labels, not a claim that their downstream behaviors were tested. Record semantic failures without tuning expected labels to observed outputs. A structural unit-test pass and real Jev semantic quality are separate results.

## Discriminating verification and later review

Controlled provider tests should fail if the batch is split, a second request/retry occurs, one target or requested field disappears, an unoffered option is accepted, scope is widened by context, malformed output becomes ready, or ambiguous count inputs receive an invented root. A successful exact-ID control must survive the same real validation path. Instrument actual transport requests, not only a wrapper call.

Independent review after implementation will inspect ownership, transport counting, option coverage and semantic honesty against this note. Live runs remain bounded to the agreed 12 single-call cases. A later integration decision requires separate public research-flow proof, including clarification/resume, retrieval, retained answer requirements and final answer assessment.