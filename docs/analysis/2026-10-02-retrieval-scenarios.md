---
title: Retrieval scenarios for the question-to-answer journey
description: Scenario catalog for the proposed retrieval flow, linked to existing repository-question research and measured baseline cases.
type: explanation
status: draft
created: '2026-10-02'
last_updated: '2026-10-02'
components: [knowledge_management, decision_kernel]
---
# Retrieval scenarios: ask a question, get an answer with sources

**Authoring provenance.** GPT-6 (`gpt-6-sol`), high reasoning, 2026-10-02, in worktree `C:\Users\Hendrik\Code\leafcutter\worktrees\knowledge-retrieval-v01` on `feature/knowledge-retrieval-v01`. The six flow files below were **uncommitted working-tree content** when inspected. Their SHA-256 hashes pin this catalog's design basis; a Git HEAD alone does not identify those bytes. This document is a proposed scenario specification, not a run record, a new acceptance criterion, or proof that the target journey exists.

| Flow shorthand | Working-tree flow and SHA-256 |
|---|---|
| M | [Main question journey](../product-truth/flows/leafcutter/retrieve-project-knowledge.flow.json) — `7AAB9E3278E8FAEC5406F1C0E9A40E63CBFCA9EE73DD49A289B86A2522E6A018` |
| Q | [Registered query](../product-truth/flows/leafcutter/retrieval-registered-query.flow.json) — `86E652C3E18424447557FB86C816E3EFDE24DAA8B993E799CC56DAB7F65719F5` |
| S | [Search preparation](../product-truth/flows/leafcutter/retrieval-search-preparation.flow.json) — `1CD8FD46FAC991AE1F2C21594171A364C31B3BBDF7F2651D273ED43095E31ECE` |
| T | [Source traversal](../product-truth/flows/leafcutter/retrieval-source-traversal.flow.json) — `C620BD22C0627B922A93D7161183761FE07BD228F9BF23C7339753AE9A863FC5` |
| B | [Query build](../product-truth/flows/leafcutter/retrieval-query-build.flow.json) — `1B4F2C447BB0EA066187076FCABD0AA710B23DE96E9F19953333DB1258C96D80` |
| C | [Current baseline](../product-truth/flows/leafcutter/retrieval-current-baseline.flow.json) — `9243FF619CFEA3284162A5EA09B4344A50A94B8250459899C695F284879F4457` |

## How to use this catalog

The [repository query catalog](2026-10-01-repository-query-catalog.md) supplies 25 role questions (`BA`, `PO`, `ITPO`, `CODER`, `QA`) and eight answer families (`RQ1`–`RQ8`). Its [source-anchored evaluation cases](2026-10-01-repository-query-evaluation-cases.json) and [runnable form](2026-10-01-repository-query-evaluation-runnable.json) retain IDs `RQE-01-P` through `RQE-06-N`. The [independent acceptance report](2026-10-01-repository-answer-acceptance.md) records **12/12 executed and passed** against an actual local database/public consumer with controlled Jev and deliberate withholding/outage cases. This bounded result samples six families. It does not execute the `RS` scenarios below, establish real-model planning quality, or prove the new multi-method target journey.

Each `RS` scenario is a **design-only, not-run** case. The question is caller input, not a request to select a backend. The host supplies authorized repository/source scope and cumulative budget. Fixture conditions must be controlled independently of Jev's choice. Flow citations use `M/Q/S/T/B/C:<step-or-branch-id>`; they refer to exact JSON `id` values, not invented ACs. `AC` references are existing requirements related to the invariant, **not** a claim that they accept the whole scenario. Gaps are explicitly named without allocating AC IDs. A future harness should save request, source bytes/revision, offered contracts/frontier, attempt IDs, chosen actions, host waits/resumes, evidence locators, budget counters, final assessment, and actual versus expected result. Grade both that the desired path remains possible and that forbidden shortcuts are rejected. An implementation may choose any justified offered method combination; no case requires a particular method merely because its question contains a keyword.

Shared oracle for every case: preserve the original question, trusted scope/source identity, separate attempts, exact field meanings, evidence locators, coverage limits and cumulative budget. A completed empty result, unsupported source, access denial, outage, stale source and exhausted budget are distinct. A retrieved item is not automatically an answer. File membership is not a call/dependency edge; a partial traversal is not an exhaustive count or proof of absence. When the source is a working tree, record file content hashes or materialized immutable bytes in addition to a revision/dirty stamp. When generation is immutable, keep its source SHA and generation distinct from historical test-run SHA.

## Entry, intent and method choice

### RS-01 — Caller asks for an answer, not an operation

- **Question / fixture:** BA-02: “Do we already specify what happens when research lacks required inputs? Show the relevant criteria.” Caller supplies only that sentence; host supplies one authorized repository, source and budget. Catalog offers exact lookup where an ID is known, search and bounded navigation.
- **When:** M:`question` → `offer-methods` → `plan`. Jev may choose a search followed by a registered query or another justified offered path; it must select offered IDs and preserve the original wording.
- **Then / fail if:** Every executed request is host-scoped and the answer cites the actual clauses or states the evidence gap. Fail if the caller must pick Neo4j/native/Cypher, a fabricated ID is sent, or an unoffered operation is executed.
- **Trace:** RQ2 / BA-02; M:`retrieve`,`assess`; related AC `KM-500e-1`, `KM-500a-2`. **Gap:** one-question interface across all target methods.

### RS-02 — Ambiguous population gets a focused clarification

- **Question / fixture:** BA-01: “How many ACs concern test writing? Exclude parent requirements.” The phrase could mean the TQ-500 family or a broader semantic topic; no family/root is supplied or authorized as the intended population.
- **When:** M:`plan` cannot establish the requested population from context and takes `clarification` → `clarification-dispatch` → `clarification-answer` → `clarification-resume`; the reply specifies one population rule.
- **Then / fail if:** The same question, source, prior evidence and remaining budget resume exactly once. A stale or authority-widening reply is rejected. Fail if “test writing” silently becomes a component, root-excluded is silently treated as terminal-leaves-only, or the wait restarts spending.
- **Trace:** RQ1 / BA-01; related `KM-500a-1`, `KM-500e-1`, `KM-500e-3`; historical control `RQE-01-P/N`. **Gap:** target multi-method clarification binding.

### RS-03 — Known exact ID can take a simple route

- **Question / fixture:** QA-01: “For KM-500c-2, what must tests demonstrate?” The ID is present, the registered exact-source contract is offered, and its required arguments are trusted and complete.
- **When:** M:`plan` may choose Q:`catalog`; Q:`inputs` chooses known-value bypass and Q:`execute` runs once. M:`compare` reports one attempt's usefulness without declaring a comparative winner; M:`assess` checks requested clauses.
- **Then / fail if:** Source ID, revision, path and clause locator accompany the answer. Fail if a term-generation or query-build handoff is mandatory, or a one-attempt comparison claims that the method beat an untried alternative.
- **Trace:** RQ2 / QA-01; Q:`prepare-request`,`execute`; related `KM-500a-2`, `KM-500e-2`; historical `RQE-02-P/N`.

### RS-04 — Relevant advice cannot choose for Jev or widen access

- **Question / fixture:** ITPO-03: “Can the catalog answer which tests cover this component?” One advisory strategy record from a previous run recommends a graph query but is pinned to another source/version; a second is compatible but only suggests candidate methods.
- **When:** M:`offer-methods` checks compatibility and M:`plan` judges applicability before choosing offered methods.
- **Then / fail if:** Stale advice is ignored or flagged; compatible advice remains optional and evidentially subordinate. Fail if either record grants an operation, source or permission unavailable in this run, copies a prior answer, or bypasses source fitness.
- **Trace:** RQ7 / ITPO-03; M:`remember`; related `KM-500a-3`, `KM-500e-4`. **Gap:** automatic advisory strategy read/write, distinct from approved DecisionRecords.

## Registered query and search preparation

### RS-05 — The catalog contract must fit the answer requirement

- **Question / fixture:** BA-01 after clarification requests all TQ-500f L2/L3 descendants excluding only the root, grouped by `work_status`. One offered operation returns direct children only; another declares full descendants, field availability, completeness and population rule.
- **When:** Q:`catalog` compares purpose, inputs, outputs and limits; Q:`inputs`/`judge-inputs` accept only arguments bound to the selected contract.
- **Then / fail if:** The chosen operation can support the requested population and field or reports the precise gap. Fail if an operation is chosen by title alone, `status` substitutes for `work_status`, or direct children are presented as all descendants.
- **Trace:** RQ1 / BA-01; related `KM-500a-2`, `KM-500e-2`, `KM-500e-3`; historical `RQE-01-P/N`.

### RS-06 — Missing query input is discovered or clarified

- **Question / fixture:** BA-03: “Which requirements depend on the query-result field contract?” A relevant registered query needs a canonical contract ID, but no ID is in the question; a permitted bounded discovery result offers two plausible IDs.
- **When:** Q:`inputs` chooses discovery or clarification; Q:`prepare-request` can issue a typed host handoff; Q:`validate-inputs` checks matching wait, source/version and required fields; Q:`judge-inputs` either executes a justified binding or asks which contract is meant.
- **Then / fail if:** An invented ID and structurally valid but semantically unsupported argument never reach Q:`execute`. The original need survives the wait. Fail if term-only help accidentally executes a full search child or duplicate resume executes twice.
- **Trace:** RQ4 / BA-03; related `KM-500a-1`, `KM-500a-2`. **Gap:** proposed query-argument preparation handoff.

### RS-07 — Caller keywords suffice without model generation

- **Question / fixture:** BA-02 with optional keywords “missing research input; clarification; resume”; an offered keyword search contract accepts them and its source/filter is authorized.
- **When:** S:`terms` records caller origin; S:`decide-terms` uses `known-terms`; S:`search` executes once and S:`return-attempts` sends its result to M:`compare`.
- **Then / fail if:** No S:`request-terms`/`generate` handoff occurs. Terms are attached to this contract/version/source and are never cited as facts. Fail if search results are silently combined or answered inside the child before shared comparison.
- **Trace:** RQ2 / BA-02; related `KM-500e-1`, `KM-500c-2`. **Gap:** target model-neutral search preparation.

### RS-08 — Optional term generation is bound and checked

- **Question / fixture:** PO-02: “What prevents us from saying KM-500 is ready for everyday use?” The selected search contract needs terms, useful caller/known terms are absent, and host budget permits one optional generation request.
- **When:** S:`request-terms` binds the question, approved context and selected method/query/version/source; S:`generate` proposes exactly five distinct nonempty terms; S:`validate-terms` verifies matching resume; S:`judge-terms` accepts or rejects usefulness.
- **Then / fail if:** Only accepted terms run S:`search`; five suggestions remain search inputs, never answer evidence. A four-term, duplicate, foreign-version or stale-response payload causes bounded correction or an explicit limitation without search. Fail if another model is treated as a different product contract.
- **Trace:** RQ3 / PO-02; related `KM-500e-1`. **Gap:** optional five-term host action and its validation.

### RS-09 — Multiple searches stay separate until shared comparison

- **Question / fixture:** ITPO-01 asks for ADRs and contracts governing a retrieval operation. Offered keyword and ready vector methods cover complementary sources; one returns an ADR clause, the other returns a relevant schema locator, and both fit the same trusted scope.
- **When:** M:`plan` may choose both; S:`strategy`/`search` prepare and execute each accepted contract separately; S:`return-attempts` hands both to M:`compare` once.
- **Then / fail if:** Attempts retain separate terms, filters, model/version where relevant, budget and locators. M:`combine` may merge selected complementary evidence later. Fail if selecting both implies mandatory parallelism, every method is run automatically, or a vector candidate without readiness executes.
- **Trace:** RQ2 / ITPO-01; M:`retrieve`,`compare`,`combine`; related `KM-400c-4`, `KM-500c-2`. **Gap:** multi-method target orchestration.

### RS-10 — Failed search preserves a useful sibling result

- **Question / fixture:** QA-04 asks which fixtures distinguish no matching tests from unsupported mapping. Keyword search returns a cited fixture; vector search times out after spending part of the run budget.
- **When:** S:`search` returns two separate outcomes; M:`compare` considers both, and M:`assess` checks whether the fixture alone answers the question.
- **Then / fail if:** The timeout is visible, useful evidence survives, and a permitted changed method/frontier may continue within remaining budget. Fail if timeout becomes “no matching tests,” erases the keyword result, resets budget, or causes an unchanged retry loop.
- **Trace:** RQ6 / QA-04; M:`retry`,`partial`; related `KM-500c-2`, `KM-500c-3`. **Gap:** cross-method failure retention.

## Graph and repository navigation

### RS-11 — Follow declared graph edges with direction and scope

- **Question / fixture:** BA-03 asks which requirements directly depend on `TQ-500f-2`. Graph frontier offers that node and typed incoming `depends_on` neighbors; its serving manifest includes the relation.
- **When:** T:`offer` exposes actual candidates; T:`frontier` chooses incoming neighbors; T:`validate` checks IDs/relation/revision; T:`read` returns attributable edge directions and source locators.
- **Then / fail if:** The answer states “direct declared dependents” and the inspected depth. Fail if an outgoing edge is reversed, hierarchy is called a blocker, or one-hop evidence becomes a transitive/code-impact claim.
- **Trace:** RQ4 / BA-03; related `KM-500f-1`, `KM-400a-3`; historical `RQE-03-P/N`. **Gap:** offered graph-node/edge navigation in the target journey.

### RS-12 — Follow repository folders and files without inventing dependencies

- **Question / fixture:** CODER-01: “Where does `work_status` travel from AC YAML into returned evidence?” A pinned repository frontier offers relevant directories and files, including the canonical loader and disclosure code, under an authorized read root.
- **When:** T:`frontier` chooses observed directories/files; T:`validate` checks each path; T:`read` opens bounded excerpts and records path, content hash/immutable source, line locator and truncation.
- **Then / fail if:** The answer distinguishes an inspected field mapping from an inferred handoff and names uninspected stages. A directory/file relationship is only navigation evidence. Fail if file presence proves a call graph, an unseen path is opened, or a dirty working-tree file is labeled merely by a commit SHA.
- **Trace:** RQ5 / CODER-01; related `KM-500f-4`, `KM-400d-2`. **Gap:** bounded code folder/file traversal.

### RS-13 — Cyclic frontier does not repeat completed reads

- **Question / fixture:** ITPO-02 asks for consumers of evidence provenance. The graph exposes A→B→A and a useful unvisited C; checkpoint records A and B as visited with their attempt IDs.
- **When:** T:`validate` rejects the visited cycle; T:`retain` resumes at an observed unvisited frontier if useful and within budget.
- **Then / fail if:** A and B are not read again, C may be read once, and visited/attempt state survives a matching resume. Fail if depth, elapsed time, scan entries, bytes or read count reset; a returned-candidate cap alone is not sufficient.
- **Trace:** RQ4 / ITPO-02; T:`continue`; related `KM-400d-3`, `KM-500c-3`. **Gap:** general traversal state and multi-axis limits.

### RS-14 — Escaped or stale path is refused without losing history

- **Question / fixture:** CODER-05 asks about a field omission. A proposed path leaves the authorized root, or a previously observed file has changed before a working-tree read; an earlier valid excerpt already exists.
- **When:** T:`validate` checks observed candidates, root, source binding and byte identity; T:`retain` records refusal and prior evidence.
- **Then / fail if:** No escaped/stale read occurs, no scope broadening happens, and the answer may use the earlier excerpt with limits. Fail if Jev's selection overrides System validation or a dirty/revision stamp is treated as a byte pin.
- **Trace:** RQ5 / CODER-05; related `KM-400a-5`, `KM-400d-2`. **Gap:** repository navigation source-byte pinning.

### RS-15 — Partial navigation cannot prove absence or exact totals

- **Question / fixture:** BA-01 asks for a count; folder or graph traversal returns a bounded first page with `truncated=true`, while another observed frontier remains unread.
- **When:** T:`read` reports the boundary; T:`judge` may continue or return partial; M:`assess` considers the original count requirement.
- **Then / fail if:** Discovered IDs may be listed as a lower bound, with unresolved frontier and no exact denominator. Fail if “no more files in this page” becomes “no other ACs exist,” or a positive Jev judgment creates `exact_total`.
- **Trace:** RQ1 / BA-01; M:`partial`; related `KM-500e-3`, `KM-500c-2`; historical `RQE-01-N`. **Gap:** traversal completeness contract.

### RS-16 — Switch method after a bounded dead end

- **Question / fixture:** QA-02 asks for actual proof of completed KM-500 ACs. A graph traversal finds declared `covered_by` links but no run receipts; an offered repository-file path can reach a historical report.
- **When:** T:`judge` chooses `fallback`; T:`retain` returns the graph attempt; M:`compare` records its limited usefulness, M:`remember` records bounded advice, and M:`alternative-method` returns to M:`plan` with remaining budget.
- **Then / fail if:** The second method can add separately sourced report evidence while preserving graph declarations. Fail if a traversal child recursively starts untracked search, the previous attempt disappears, or a declared test path is labeled executed proof.
- **Trace:** RQ6 / QA-02; related `KM-500f-2`, `KM-500c-2`; historical `RQE-04-P/N`. **Gap:** target cross-method continuation.

## Evidence, comparison and answer

### RS-17 — Compare observed attempts against the same question

- **Question / fixture:** ITPO-03 asks whether tests covering a component can be listed. A registered query returns only AC→component links; a file search finds a test manifest with unknown completeness. Both are observed under the same source and budget.
- **When:** M:`compare` judges each for the original component-to-tests question and may choose a tie, incomparable result, no winner or complementary evidence; M:`remember` records the actual judgment.
- **Then / fail if:** The comparison says which required path/field each attempt lacks and does not call a method universally superior. Fail if a higher lexical score becomes answer completeness, or different revisions/budgets are interpreted as a causal A/B win.
- **Trace:** RQ7 / ITPO-03; related `KM-500e-4`, `KM-500c-2`. **Gap:** shared observed-attempt comparison and advisory record.

### RS-18 — Deduplicate records while keeping every provenance path

- **Question / fixture:** BA-02 receives the same canonical AC from registered query and keyword search, with different excerpts and attempt IDs, plus one distinct ADR.
- **When:** M:`compare` selects complementary evidence; M:`remember` records the comparison; M:`combine` deduplicates canonical identity/overlapping chunks; M:`rank` orders for the question.
- **Then / fail if:** One AC identity remains with both supporting attempt/source locators, the ADR remains distinct, and all coverage limits survive. Fail if deduplication erases a citation, merges different revisions as one record, or converts two partial sets into complete coverage.
- **Trace:** RQ2 / BA-02; related `KM-500e-2`, `KM-500c-2`. **Gap:** target evidence combination/ranking.

### RS-19 — Successful execution with missing requested field stays unresolved

- **Question / fixture:** BA-01 requests `work_status` counts. Retrieval executes successfully and returns 15 AC IDs and lifecycle `status`, but the required `work_status` field is withheld from disclosure.
- **When:** M:`assess` compares actual fields and population to the original question after M:`return-evidence`.
- **Then / fail if:** Result states that retrieval executed but work-status grouping is unresolved; it may cite the known IDs without assigning done/todo counts. Fail if `status` is substituted, a missing field is filled from model memory, or `ok` means answered.
- **Trace:** RQ1 / BA-01; related `KM-500e-2`, `KM-500c-2`, `KM-500g-1`; historical `RQE-01-N`.

### RS-20 — Complete enumeration and source-backed exact count

- **Question / fixture:** BA-01 clarifies TQ-500f root-excluded descendants at an immutable source. A population operation supplies all pages, stable IDs, `level`, `work_status` and independent complete-population proof; the controlled historical oracle is 15 descendants, five done and ten todo at its own pinned revision.
- **When:** M:`combine` deduplicates IDs and M:`assess` verifies the requested population and field for every member before M:`finish`.
- **Then / fail if:** An exact count is allowed only for the same verified revision/population, with 15/5/10 asserted only in the historical fixture. Fail if the final continuation page alone, 11 terminal leaves, a different revision or a partial graph walk inherits those totals. A complete accumulated enumeration with independently established coverage can justify an exact total.
- **Trace:** RQ1 / BA-01; related `KM-500e-3`; historical `RQE-01-P` and independent acceptance report.

### RS-21 — Answer wording must preserve limits and citations

- **Question / fixture:** ITPO-04 asks whether a merge reached the graph. Evidence contains requested SHA, published SHA and readiness but no actual merge-trigger receipt; wording is needed to explain the distinction.
- **When:** M:`dispatch-wording` sends a typed accepted-evidence handoff; M:`wording` returns prose; M:`check-wording` validates citations, limits and matching resume; M:`judge-wording` accepts, revises within bounds or stops.
- **Then / fail if:** The answer can state the observed publication SHA/readiness while withholding the claim that a merge-triggered job ran. Fail if candidate prose is returned before acceptance, removes the missing-trigger limitation, invents a trace, or an invalid resume causes a second retrieval.
- **Trace:** RQ8 / ITPO-04; related `KM-500g-2`, `KM-500d-2`. **Gap:** target wording handoff and Jev acceptance.

### RS-22 — Structured facts can bypass extra wording

- **Question / fixture:** QA-01 requests the exact title and criteria locator for known `KM-500c-2`; accepted evidence already has the structured fields needed for a concise response.
- **When:** M:`assess` finishes and M:`dispatch-wording` selects structured-facts bypass.
- **Then / fail if:** M:`respond` returns the unchanged accepted fields and citations without M:`wording` or M:`judge-wording`. Fail if bypassed facts are silently paraphrased into unsupported claims or a host LLM is invoked despite no wording need.
- **Trace:** RQ2 / QA-01; related `KM-500e-2`. **Gap:** proposed conditional synthesis bypass.

## Failure, growth and learning boundaries

### RS-23 — Missing source fact, field mapping and query are different

- **Question / fixture:** ITPO-03 asks for tests covering a component. Three controlled manifests differ: (a) canonical source lacks test links, (b) links exist but are unprojected/undisclosed, (c) links are mapped and disclosed but no offered query expresses the requested path.
- **When:** M:`offer-methods`/`plan` and B:`gap` inspect actual source fitness before build eligibility.
- **Then / fail if:** (a) is source fact gap, (b) mapping/disclosure gap, (c) eligible missing-query opportunity if no other offered method answers. Fail if all three trigger coding-agent build, or an unsupported source is reported as completed zero results.
- **Trace:** RQ7 / ITPO-03; related `KM-500a-3`, `KM-500e-4`, `KM-500b-1`; historical `RQE-05-P/N` uses a controlled hypothetical operation gap.

### RS-24 — Query build is governed and resumes once

- **Question / fixture:** A supported mapped relation is answerable in principle, no offered query fits, and an identical active build request already exists for the same source/requirements.
- **When:** B:`gap` qualifies the gap; B:`build-request` deduplicates the request; B:`author` supplies bounded candidate plus contract/tests/evaluation; B:`admit` independently verifies permission; B:`resume` executes only an admitted version and returns its attempt to M:`compare`.
- **Then / fail if:** Waiting need, original question, source and prior evidence survive. A rejected candidate follows `admission-failed` and is never executed; later matching needs reuse the registered version. Fail if arbitrary Cypher is admitted, source facts are fabricated, or duplicate resumes execute twice. Proper-query authoring architecture remains an open design decision.
- **Trace:** RQ7 / ITPO-03; related `KM-500b-1`, `KM-500c-1`, `KM-500c-3`. **Gap:** target integration of governed build into multi-method comparison.

### RS-25 — One failure is not global failure; no useful route stops honestly

- **Question / fixture:** BA-05 asks whether a proposed behavior conflicts with ACs/ADRs. The selected query is unavailable; a permitted search can still inspect relevant clauses. In a second fixture, all offered routes are denied or exhausted with no useful evidence.
- **When:** M:`retrieve` records the query outage and M:`compare`/`assess` considers a changed route; only the second fixture reaches M:`blocked`.
- **Then / fail if:** First fixture may return sourced partial findings with the outage disclosed. Second names the actual authority/source/budget block, never “no conflicting AC exists.” Fail if outage is converted to empty success or identical no-progress attempts repeat.
- **Trace:** RQ2 / BA-05; related `KM-500c-2`, `KM-500c-3`; historical `RQE-06-N` tests an unavailable boundary.

### RS-26 — Focused clarification after evidence preserves findings

- **Question / fixture:** PO-01 asks what to prioritize next. Retrieved ACs have priorities and work status, but no agreed benefit-ranking policy; useful findings are already present.
- **When:** M:`assess` selects `clarify-after-evidence`; System dispatches a bounded policy choice, validates the matching answer and resumes under the same source/budget.
- **Then / fail if:** The answer separates observed status from recommendation under the supplied policy. If policy is unavailable, return an explicit unresolved recommendation and still expose supported findings. Fail if Jev invents value weights or the clarification wipes earlier evidence.
- **Trace:** RQ3 / PO-01; related `KM-500f-3`, `KM-500a-1`. **Gap:** target post-evidence clarification.

### RS-27 — Budget exhaustion yields an attributable partial answer

- **Question / fixture:** QA-02 requests proof levels for completed KM-500 ACs. The run has cited declarations and one historical report, but further file reads exceed cumulative byte/time budget before all ACs are inspected.
- **When:** T:`read`/`retain` and M:`assess` preserve consumed limits and useful evidence; M:`partial` or `blocked` reports the remaining gap.
- **Then / fail if:** Supported items retain per-source proof level and unknown items remain unknown. Fail if continuation resets limits, a truncated report is treated as full proof, or “all completed ACs” is claimed from the sampled set.
- **Trace:** RQ6 / QA-02; related `KM-400d-4`, `KM-500f-2`, `KM-500c-3`.

### RS-28 — Advisory learning records observation, not truth or approval

- **Question / fixture:** ITPO-05 asks why `ok` omitted work statuses and where its trace is. Two attempts yield a query result missing the field and a source quote showing the disclosure gap; no verified remote trace is available.
- **When:** M:`compare` records the observed strengths/limits; M:`remember` writes a typed proposed strategy record before M:`combine`, with original question, method/query/version, terms, source/model versions, budgets, attempt/evidence IDs, comparison outcome and limitations. M:`respond` may append only the actual final answer outcome if storage exists.
- **Then / fail if:** A no-winner/tie is representable, storage failure is visible without erasing evidence or repeating retrieval, and future reuse cannot grant authority or replace proof. The answer diagnoses only the inspected field gap and says trace verification is unavailable. Fail if the record is labeled human-approved, becomes model training, fabricates a URL/root cause, or stores a final outcome before assessment.
- **Trace:** RQ8 / ITPO-05; M:`compare`,`remember`,`respond`; related `KM-500g-1`, `KM-500g-2`; historical `RQE-06-P/N`. **Gap:** automatic typed advisory strategy storage, outside current approved DecisionRecord publication.

### RS-29 — Non-reading traversal decision bypasses read and post-read judgment

- **Question / fixture:** CODER-01 asks for the `work_status` field path. At a valid offered file frontier, an earlier source excerpt already answers the requested mapping, or Jev chooses a different method, clarification or stop before any further read.
- **When:** T:`frontier` selects a bounded return/switch/clarify/stop decision; T:`validate` accepts it; T:`nonreading` routes directly to T:`retain` without T:`read` or T:`judge`. A return sends the retained attempt to M:`compare`; a switch follows the shared comparison/advisory route before M:`plan`.
- **Then / fail if:** Prior attempts, evidence, frontier, visited state and remaining budget stay intact; no source read or post-read judgment is charged. Fail if a non-reading choice is converted into a read, silently discarded, or allowed to bypass validation. An invalid non-reading choice is refused without widening scope.
- **Trace:** RQ5 / CODER-01; related `KM-500c-2`, `KM-500c-3`. **Gap:** target traversal decision bypass and shared comparison integration.

## Coverage and next proof

| Dimension | Scenario IDs | Existing bounded evidence versus proposed proof |
|---|---|---|
| Persona families | RS-01–29 | RQ1–RQ8 and all five role groups represented; original 25 question wording remains in the linked catalog. |
| Existing controlled eval lineage | RS-02/05/15/19/20 → RQE-01; RS-03 → RQE-02; RS-11 → RQE-03; RS-16 → RQE-04; RS-23 → RQE-05; RS-25/28 → RQE-06 | The 12 RQE cases were run as reported; these RS variants and target routes were not. |
| One or multiple methods | RS-01/03/04/09/10/16/17/18 | Needs target-run evidence with actual offered contracts, Jev selections and shared comparison. |
| Registered query and inputs | RS-03/05/06/24 | Existing registered-query baseline is bounded; optional argument handoff and target join need proof. |
| Search and five terms | RS-07–10 | Optional model-neutral generation, validation, separate attempts and shared comparison need proof. |
| Graph/file navigation | RS-11–16/27/29 | Observed candidates, byte binding, non-reading decisions, cycle/budget handling and incomplete coverage need proof. |
| Answer and learning | RS-17–22/26/28 | Field/count/proof distinctions have bounded existing evidence; target combination, wording and advisory memory need proof. |
| Failure and capability repair | RS-10/14/15/23–27 | Distinct no-result/outage/denial/unsupported/partial outcomes and admitted build continuation need proof together. |

To make a scenario runnable, freeze a source corpus and independent oracle, define the offered contract/frontier and actor controls, then assert the entire public result plus attempt/continuation trace. Reuse the `RQE` corpus for its six established families; add controls for RQ3 and RQ5 and for the new multi-method/traversal paths. Record real Jev/provider runs separately from scripted Jev/local fixtures. None of the RS cases has been executed in this authoring work.
