---
title: "Colony Memory Stage 0 Delta Design - Part 2 of 4"
description: "Stage 0 delta design for the Neo4j colony memory concept, part 2 of 4: the reuse / adapt / replace / add verdict for every concept element, and the minimal Neo4j MVP (nodes and edges, five registered queries mapped to live-QA lessons, ingestion prerequisites, Mode 0 behaviour, explicit non-goals)."
type: explanation
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
related_docs:
  - docs/analysis/2026-10-01-colony-memory-stage0-delta.md
---

> Part 2 of 4 of the Colony Memory Stage 0 delta design ([previous part](2026-10-01-colony-memory-stage0-delta.md) | [next part](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md)). Evidence tags A, B, C, L, K and BOOT are defined in [part 1](2026-10-01-colony-memory-stage0-delta.md#evidence-legend).

## (b) Reuse / adapt / replace / add

| # | Concept element | Verdict | What exactly | Evidence |
|---|---|---|---|---|
| 1 | Three layers (§6): Git, Neo4j, Langfuse | ADAPT | Keep the shape ADR-057/058 already use. Swap the middle layer to Neo4j and widen it from compact statistics to "compiled declared graph plus learned memory". The run root `.leafcutter/kernel/` and the checkpointer stay authoritative for run state (ADR-057 §9). | B §3.2; C §2a |
| 2 | Declared graph producer (§6.2, §9.1) | REUSE + ADAPT | `knowledge_query.build_knowledge_map()` is the single node/edge producer. A sibling exporter imports it and joins properties; no fork of its edge logic. `knowledge_query.py` is 1,794 lines and may not grow (GE-127b-1 ratchet). | B §1.1, §5 OQ1 |
| 3 | AC node properties | REUSE | `get_ac_index(store_root)` in `scripts/commit_guardian/_ac_store_index.py` L234: one fingerprint-cached dict of every AC with all fields. The map's AC nodes carry no status, priority or phase. | B §1.2 |
| 4 | Component source (`components.json`) | REUSE | 45 snake ids, `type`, `status`, `primary_code`. Expand `primary_code` directories into File nodes by longest prefix, or Q-B returns `kernel/` instead of `kernel/persistence/*`. | B §1.3, §4.2 |
| 5 | ADR and doc sections | ADD | A Markdown heading parser (none exists); Section nodes keyed `ADR-057#alternatives`, ADRs first. | B §4.2 Q-C |
| 6 | IDs (§11) | REPLACE the concept scheme with a projection | Node key = (repository_id, kind, id), where id is the existing string: `ACS-100`, `ADR-057`, `ac_store`, `phase_1`, repo path. No `ac:x:y`, `adr:x:y` or `component:x`. Learned ids reuse the kernel `ID_PATTERN` (`dec-<16 hex>`). | A §2, §6.1 |
| 7 | Provenance (§12) | ADD in the ingester | Git SHA, dirty flag, `repository_id`, path, `parser_version`, `last_indexed_at`. No declared artifact stores a SHA and no `repository_id` exists; the pattern exists as `SourceVersion{commit, dirty}` in `kernel/contracts/evidence.py`. | A §4 |
| 8 | `ColonyMemory` port (§25) | ADD (carries ADR-057 §3) | New package `kernel/memory/`, sibling to `kernel/persistence/`: Protocol, `NullColonyMemory`, `Neo4jColonyMemory`. Synchronous like `GapStorePort`; selected once in `bootstrap.build_environment`; no URI branches elsewhere. Read method `run_registered_query(query_id, params)`. | B §2.3 (1), OQ |
| 9 | Capability gaps (§23, §29-F) | REUSE + ADD a sink | `GapStorePort` and `FileGapStore` stay authoritative. `publish_gap` (`kernel/persistence/gap_store.py` L128) also calls `ColonyMemory.record_capability_gap`, best effort: swallow and log, like its existing OSError path. | B §2.3 (2) |
| 10 | Retrieval from the graph (§14) | ADAPT | Add `graph_query` to `SourceConfig.kind` (`kernel/config.py` L148, regenerated schema), a `query_ids[]` field, `NATIVE_KINDS` (`kernel/capabilities/retrieval/executor.py` L54) and a readiness branch in `planning._native_available`. Rows become `Candidate(kind=KNOWLEDGE_NODE, strategy="graph_query:<id>")`, so rerank, evidence and coverage stay unchanged. | B §2.2, §2.3 (3) |
| 11 | Decision persistence (§15, §29-E) | ADD | A `DecisionRecord` envelope. Today's `Decision` (`kernel/contracts/decision.py` L109) holds ids only: no option or criterion text, no decision type, no scope components, no approver, no trace id, no revision. Write at approval (`_apply_decision_approval`, `kernel/capabilities/decision/approvals.py` L111) as `approved`, and at `finalize` (`kernel/scheduler/nodes_lifecycle.py` L262) as `proposed`. Deterministic id plus MERGE keeps resume idempotent. | B §2.1, §2.3 (4) |
| 12 | Merge-driven ingestion (§8) | ADD | A separate trusted CLI/CI step outside the kernel. It writes only declared nodes and runs from the installation, never from the scoped repo (lesson 15). Incremental by file hash. The kernel writes only learned nodes. Staleness: indexed commit vs `Scope.revision.commit` gives a limitation, not a failure. | B §2.3 (3, 5); A §6.4 |
| 13 | Registered parameterized queries (§14 order) | ADD | Five queries (§(c) below). No text-to-Cypher. | B §4.2 |
| 14 | ADR-057/058 carry-over | REUSE most | **Kept:** port, Null and startup choice (§3); optional by default; enablement semantics and the `LEAFCUTTER_SELF_LEARNING=false` opt-out (§4, new variable names); hot path never reads Langfuse (§5, ADR-058 §6); mandatory context dimensions (§7, now APPLIES_TO/ABOUT edges); run-root separation (§9); staged adoption (§10, plus a new READ row). **Superseded:** §1 (statistics only), §2 (PostgreSQL), the §3 implementation list, the §4 variable names, §6 (tables), the Postgres Alternatives. ADR-058 is unchanged except the §6 layer table. | B §3.2, §3.3 |
| 15 | Policy, Workflow nodes | DEFER | No declared entity. Later candidates: `templates/rules/*.md` (glob-scoped) and workflow file stems, after the ADR-054 maturity model. | A §1.5, §1.6 |
| 16 | Capability node | DEFER | None on main; the K registry (7 entries) after PR #973 merges. | A §1.7 |
| 17 | Class, Function, API | DEFER | No in-repo symbol index. jcodemunch and serena are external MCP servers; depending on them breaks Mode 0. | B §1.3 |
| 18 | Mistake, Lesson, ExecutionPattern, Memory (§9.2) | DEFER to concept Stage 2 | The knowledge-emission pipeline and `config/feedback_categories.yaml` are the later Lesson source and type seed. | B §1.3; A §5 |
| 19 | Vector precedent (§15) | DEFER to concept Stage 3 | Version 1 filters precedents by component and decision type. | B §4.2 Q-E |
| 20 | Managed Mode 2 (§25, §34) | DEFER | Needs a PO and roadmap decision first. | C §3 (I) |
| 21 | KnownIssue (not in the concept) | ADD later | Declared, one file each, `components[]`; two id forms and two collisions. | A §1.11 |

## (c) Minimal Neo4j MVP

### c.1 Node and edge set

| Node | Source | Key properties | Id (existing) |
|---|---|---|---|
| Repository | Ingester (git remote or user-supplied) | repository_id | see ADR-061 |
| Component | `docs/components.json` | name, type, status, detail_ref | `ac_store` |
| AcceptanceCriterion | `get_ac_index` | title, level, status, work_status, priority, readiness, roadmap_phase, path | `ACS-100` |
| ADR | ADR frontmatter | title, status, path | `ADR-057` (integer form, not the filename stem) |
| Section | New heading parser (ADRs; later `docs/analysis` and component docs) | heading, number, start_line, end_line, text_hash | `ADR-057#alternatives` |
| File | `knowledge_query` files plus `primary_code` expansion | path, kind (code, test, config, doc), missing | repo path |
| Ticket | Ticket frontmatter | status (frontmatter, not folder), path | repo path (epic stems repeat) |
| Phase | `docs/roadmap.json` | status | `phase_1` |
| Test | File with kind=test, from `covered_by` paths and the `# covers:` scan | path | repo path (function level deferred) |
| Decision (learned) | Kernel through `ColonyMemory` | question, decision_type, options_json, selected_option, approval_status, approver, langfuse_trace_id, repository_revision, created_at | `dec-<16 hex>` |

**Declared edges:**
- BELONGS_TO: AC, ADR or Ticket to Component, from `components[]`.
- DEPENDS_ON: AC to AC, true dependencies only. CHILD_OF: AC to AC, derived from the id.
- COVERED_BY: AC to test File. VERIFIES: test File to AC, from `# covers:`.
- IMPLEMENTED_BY: AC to source File only; ticket paths become TRACES_TO instead.
- PRIMARY_CODE: Component to File. RELATED_TO: ADR or doc `related_docs`.
- FILES_TOUCHED: Ticket to File. TRACES_TO: Ticket to AC, from `ac_traceability`.
- IN_PHASE: AC to Phase. HAS_SECTION: ADR to Section.

**Learned edges:**
- ABOUT: Decision to Component.
- USED_EVIDENCE: Decision to AC, ADR, Section or File.
- SUPERSEDES: Decision to Decision.

**Rules:**
- The vocabulary is closed and versioned (concept §9.3, L0-AC-14); ingest fails on an unknown label or relationship type.
- Every declared node carries origin=repository, repository_id, path, commit_sha, dirty, parser_version and last_indexed_at.
- A uniqueness constraint holds on (repository_id, id) per label.
- Deferred: Class, Function, Policy, Workflow, and also Capability, the 5.2k-file docs corpus, agents and skills, product-truth, glossary and KnownIssue.

### c.2 The five registered queries and the lesson rows they fix

Cypher sketches are in B §4.2. Every row returns path, commit and indexed_at, so it can become evidence with a locator; every query reports "unknown" counts instead of silent empties.

| Query | Returns | Parameters | Fixes lesson rows |
|---|---|---|---|
| Q-A `list_acs` | ACs filtered and priority-ordered | component, work_status, priority, readiness, level, phase, limit | 8 (20 of about 4,460 AC files sampled by wording); 6 (AC store and roadmap not searched); helps 5 (options grounded in the AC store) |
| Q-B `get_component_footprint` | A component's code, tests, ADRs, tickets and AC count | component, n | 6 (tests, config, tickets invisible); 11 (`kernel/persistence/*` dropped by a 20-of-511 lexical prefilter); 7 for code modules |
| Q-C `get_adr_sections` | Named sections of one ADR, or of a component's ADRs | adr or component, headings, numbers | 10 (ADR-057 §9 and Alternatives never read); 7 (design docs, once Section covers `docs/analysis`) |
| Q-D `get_implementation_state` | Component status, ADR status, ACs done/open, implementing files present/missing | component | 9 (aspirational docs satisfied "does it learn"). A signal for the coverage judge, not a verdict |
| Q-E `get_decision_precedents` | Approved decisions by type and component, with evidence and supersessions | decision_type, components, since, limit | 19 (no decision written back); 16 (approved only); 14 (stores `options[].proposed_by`) |

### c.3 Ingestion prerequisites (before Neo4j sees anything)

1. **Double-indexing in `knowledge_query`.** Every AC appears in both the `acs` and `docs` surfaces, and every ADR in `adrs` and `docs`, because `docs/` is globbed recursively. In all, 4,625 ids sit on more than one node. Exclude the AC and ADR directories from `docs`, or dedupe by path [A §0].
2. **Id collisions.** 55 epic sub-ticket stems repeat, so tickets are keyed by path. ADR nodes use the filename stem, so ADRs are keyed by the integer [A §1.4, §1.10].
3. **Kebab/snake twins.** Component hubs exist in both spellings (38 snake, 28 kebab). Join on `components[]` snake ids only, and map kebab doc names through an explicit table: 7 component docs and 20 registry entries do not pair [A §1.1].
4. **Overloaded edges.** Split them into typed relationships:
   - `depends_on` into parent, pattern and dependency;
   - `covered_by` into child AC and test path;
   - `implemented_by` into ticket and source path (decline SHAs).
   Also normalise `doc_links.relationship` (about 40 spellings) to a closed set [A §1.2, §6.2].
5. **One status axis per entity.**
   - AC: `status` (lifecycle) and `work_status` (delivery) are the query axes; `readiness` and `req_status` stay properties.
   - Ticket: frontmatter `status`. Folder and frontmatter disagree in hundreds of files.
   - Component: `status`.
   - Normalise nulls (150 `work_status`, 70 `level`) to an explicit `unknown` [A §6.5; B §1.2].
6. **Exclusions.** Skip `.leafcutter/` (the deployed copy of scripts and config) and `worktrees/` [A §4].
7. **Dropped edges.** `validate_edges_integrity` drops edges to absent targets by design. The ingester must count and report them, not hide them [A §0].

Whether fixes 1-4 land in `knowledge_query` itself (Stage 1 scope) is decision 7 in [part 4](2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md).

### c.4 Mode 0: no Neo4j configured

- **Selection.** With no `LEAFCUTTER_NEO4J_URI`, or with the opt-out set, the kernel uses `NullColonyMemory`, chosen once at startup (ADR-057 §3 carried over).
- **Retrieval.** `graph_query` sources report `unavailable` with a reason from the readiness check, never an empty result. The `repo_text` and `knowledge_map` sources still serve the need (L0-AC-07).
- **Writes.** Record calls are no-ops. Gaps still go to `FileGapStore`; decisions still sit in the checkpoint and `report.json`. Learning is off: there is no precedent retrieval.
- **Dependency.** The Neo4j driver is an optional extra, imported lazily inside `Neo4jColonyMemory` only, so the tests pass with the driver absent.
- **Tests.** An in-memory test double (like `kernel/persistence/memory.py`) is needed for unit tests either way. It is not a persisted store.
- **Unreachable store** (configured but down, ADR-057 Open Question 6). Recommended: same as Mode 0 for that run, with one warning and a run limitation. ADR-059 must say so.
- **File store.** A persisted `FileColonyMemory` is decision 5.

### c.5 Explicitly not in the MVP

- **From concept §29:** PR and dirty-worktree overlays, a full code-function graph, automatic memory promotion, self-modifying routing, pheromone decay, structural graph similarity, automatic policy updates, cross-customer learning, a managed service.
- **Also excluded:**
  - nodes: Class, Function, API, Policy, Workflow, Capability, Mistake, Lesson, ExecutionPattern;
  - retrieval: embeddings and vector indexes, text-to-Cypher;
  - writes: capability statistics, any kernel write to a declared node, glossary writes;
  - influence: any routing influence or threshold change from history;
  - scope: the docs corpus, product-truth, KnownIssue, a shared multi-repo store and its privacy policy (ADR-057 Open Question 1 stays open).
