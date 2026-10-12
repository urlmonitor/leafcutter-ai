---
title: "Colony Memory Stage 0 Delta Design - Part 1 of 4"
description: "Stage 0 delta design for the user's Neo4j colony memory concept, checked against main, kernel V0 (PR 973) and the uncommitted Postgres ADR-057/058. Part 1 of 4: summary, evidence legend and answers to the concept's ten Stage 0 questions (section 38)."
type: explanation
status: draft
created: 2026-10-01
last_updated: 2026-10-01
components:
  - knowledge_management
  - knowledge_system
related_docs:
  - docs/analysis/2026-10-01-neo4j-colony-memory-concept.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md
  - docs/analysis/2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md
---

> Stage 0 output (concept §29, §30 "Stage 0") for the [Neo4j colony memory concept](2026-10-01-neo4j-colony-memory-concept.md). Part 1 of 4 (first part | [next part](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md)). Docs only: no Neo4j schema is final, no code or config changed. Nothing here is decided until the user answers the [decisions in part 4](2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md).

# Colony Memory Stage 0: delta design

| Part | Content |
|---|---|
| 1 (this) | Summary, evidence legend, (a) answers to the ten questions of concept §38 |
| [2](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md) | (b) reuse / adapt / replace / add table, (c) minimal Neo4j MVP |
| [3](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md) | (d) live-QA lessons mapped to the concept, approval-provenance gap, (e) ADR plan, (f) ownership and propagation |
| [4](2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md) | (g) conflicts and the eight decisions needed from the user, each with a recommendation |

Concept sections by part: 1-4 [p1](2026-10-01-neo4j-colony-memory-concept.md), 5-8 [p2](2026-10-01-neo4j-colony-memory-concept-2-layers-truth-sync.md), 9-13 [p3](2026-10-01-neo4j-colony-memory-concept-3-graph-model-ids-provenance.md), 14-18 [p4](2026-10-01-neo4j-colony-memory-concept-4-retrieval-and-memory-capture.md), 19-24 [p5](2026-10-01-neo4j-colony-memory-concept-5-reinforcement-and-gaps.md), 25-29 [p6](2026-10-01-neo4j-colony-memory-concept-6-deployment-diagrams-mvp.md), 30-31 [p7](2026-10-01-neo4j-colony-memory-concept-7-roadmap-and-l0-acs.md), 32-33 [p8](2026-10-01-neo4j-colony-memory-concept-8-adrs-and-propagation.md), 34-38 [p9](2026-10-01-neo4j-colony-memory-concept-9-business-risks-next-action.md).

## Evidence legend

Citations use the tags below. The three research files and the lessons file are session scratch files (not in the tree), so every claim also names the repository path it rests on. `<scratch>` = `C:\Users\Hendrik\AppData\Local\Temp\claude\c--Users-Hendrik-Code-leafcutter\fc0a87d9-5187-490f-8da4-30cc8d0a6b33\scratchpad`.

| Tag | Source | Scope |
|---|---|---|
| A | `<scratch>\stage0\A-entities-ids-links.md` | Declared entities, ids, links, provenance, vocabularies on main @ 73dce349 (measured 2026-10-01) |
| B | `<scratch>\stage0\B-graph-persistence-memory.md` | Graph and index machinery, kernel V0 ports and seams, the Postgres concept, the smallest projection and five queries |
| C | `<scratch>\stage0\C-ownership-conflicts-adrs.md` | Artifact owners, conflicts, ADR create-vs-update, numbering |
| L | `<scratch>\lessons-2026-10-01-live-qa.md` | 19 lesson rows from four live QA rounds and the dogfood run of kernel V0 |
| K | Kernel V0, PR #973, branch `feature/kernel-v0-p10` | ADR-052..056, `kernel/`, `config/capability_registry.json` |
| BOOT | The user's worktree `kernel-bootstrap-v0` (uncommitted, read only) | ADR-057/058, `colony-memory.md`, vision, roadmap, components |

## Summary

1. **A declared-knowledge graph already exists.** `scripts/knowledge_query.py` builds about 12.8k nodes and 33k edges from nine `config/paths.json` surfaces in about 7 s, stdlib only [A §0, B §1.1]. Neo4j should compile it plus the AC index, not replace it.
2. **The Postgres store was decided one day before the concept and exists only on paper.** ADR-057/058 are Accepted but uncommitted in BOOT; no `ColonyMemory`, driver or env var exists in code [B §3.1, C §0]. Migration is documents-only.
3. **The concept's ids do not exist.** `ac:retrieval:cache.force_refresh`, `adr:retrieval:caching-strategy` and `component:retrieval` have no counterpart; the real ids are `ACS-1300a-1-i`, `ADR-037` and `ac_store` [A §2]. Project them; node key = (repository_id, kind, id).
4. **The kernel already has the seams.** `publish_gap` (gap store write seam), `SourceConfig.kind` (source adapters), the `Decision` contract, `Scope.revision` and `RunRecord.trace` [B §2]. Missing: a cross-run memory port and a decision envelope carrying text, approver, trace and revision.
5. **Minimal MVP:** Component, AC, ADR, Section, File, Ticket, Phase and Test-as-file, plus learned Decision, read through five registered queries that answer live-QA rows 6-11, 14, 16 and 19 ([part 2](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md)).
6. **The concept misses approval provenance** (lesson 16): records cannot self-authorise, only human-approved decisions count as precedent ([part 3](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md)).
7. **ADR plan:** ADR-059 (Neo4j store, supersedes ADR-057's store choice, folds ingestion and backend abstraction), ADR-060 (source of truth and authority) and ADR-061 (ids). Candidates C and D are already ADR-053 and ADR-054.
8. **Eight decisions are needed from the user** before any ADR or code ([part 4](2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md)).

## (a) Answers to the ten questions (concept §38)

### Q1. Which parts of the proposal already exist?

| Concept element | Exists today as | Evidence |
|---|---|---|
| Compiled declared graph (§6.2, §9.1) | `knowledge_query` map: file-level nodes without structured properties, ids collide across surfaces | A §0; B §1.1; `scripts/knowledge_query.py` (`NodeRecord` L88, `EdgeRecord` L114, `build_knowledge_map` L437) |
| Git as declared truth (§6.1, §7) | AC store, ADRs, `docs/components.json`, `docs/roadmap.json`, all in Git; ADR-010 makes the AC store the authoritative backlog | A §1; C §2c |
| AC to test links (§10) | `# covers: <AC-ID>` comment tag (`COVERS_TAG_RE`, `scripts/ac_store/test_enforcement.py:57`) and `covered_by[]` paths; no decorator | A §1.3 |
| Langfuse execution history (§6.3) | ADR-058 (BOOT), the K tracer, `RunRecord.trace` | B §2.1, §3.1 |
| `ColonyMemory` port with a Null backend (§25) | ADR-057 §3 (BOOT): same name, same Null, chosen once at startup. No code | B §3.1 |
| Capability gaps as scouts (§23) | K `FileGapStore` and `publish_gap` (`kernel/persistence/gap_store.py` L128), per checkout; ADR-056 §6 | B §2.1 |
| Reinforcement safety (§19-22) | ADR-056 §2-4 and §9 (K) | C §3 (H) |
| Placement ladder (§5) and maturity chain (§2, §28) | ADR-053 and ADR-054 (K) | C §3 (C, D) |
| Constrained scope vocabularies (§16) | components, `change_target`, `risk_surface`, `doc_types`, `entry_kind`, feedback categories | A §5 |
| Learned-knowledge capture (§17) | `scripts/knowledge/emit_knowledge.py`, `harvest_learnings.py`, ADR-011/034/040: routes learnings into Git files, not a graph | B §1.3 |
| Not present | Any database or vector code, Policy entity, Workflow registry, Class/Function index, cross-run Decision persistence, Mistake/Lesson nodes | A §1.5, §1.6, §1.9; B §1.3, §2.1 |

### Q2. What are the canonical entities and ids?

| Entity | Real id | Storage | Minting and uniqueness |
|---|---|---|---|
| Component | `ac_store` (snake); kebab twin `ac-store` in the AC `component` scalar and doc filenames | `docs/components.json`, 45 entries | Hand edit; `check-components-integrity` (new entries only) |
| AC | `PREFIX-NNN[x[-N[-y]]]`, e.g. `ACS-1300a-1-i` | One YAML per AC, `docs/acceptance-criteria/<namespace>/`, 4,459 files | PO/BA highest+1; `check-ac-schema`, `check-identifier-uniqueness`; 0 duplicates measured |
| ADR | `ADR-NNN` global integer (the knowledge map uses the filename stem) | `docs/architecture/adrs/` | adr-author highest+1; `check-adr-collision` |
| Ticket | `TICKET-YYYYMMDD-<name>` or epic `NN_slug` (55 stems repeat across epics) | `tickets/**` | Generator or agents; weak |
| Roadmap phase | `phase_1` | `docs/roadmap.json` | Schema regex |
| Test | `path::function` | `unit_tests/`, `tests/` | None |
| File | Repo-relative path | Synthetic knowledge-map nodes (1,547, 434 missing) | Derived |
| Capability (K only) | `decision`, `retrieve.repository` | `config/capability_registry.json`, 7 entries | Kernel validator |
| Kernel runtime | `dec-<16 hex>`, `ev-<hash16>` | `kernel/contracts/base.py` (`ID_PATTERN`) | Pydantic |
| KnownIssue | `KI-CG-006`, `KI-CG-20260826-1612` | `docs/known-issues/` | None (two known collisions) |
| Policy, Workflow | None: rules by filename, workflows by file stem | `templates/rules/`, `templates/workflows-js/` | Filesystem |

Source: A §2.

### Q3. How are Components, ACs, ADRs, Policies, Workflows, Capabilities, Tests and code linked?

- **AC to Component:** `components[]`, snake ids, enforced. The `component` scalar is the AC namespace, not a component [A §1.2].
- **AC to AC:** `depends_on[]` mixes parent, pattern composition and true dependency; plus `parent` (77) and `superseded_by` (no existence check).
- **AC to test:** `covered_by[]` mixes child-AC ids (4,272) and test paths (772, 738 exist). The only trusted Test-to-AC edge is the `# covers:` tag, enforced diff-scoped; four regex sites drift (data-map Gap 11) [A §1.3].
- **AC to code or ticket:** `implemented_by[]` mixes ticket paths (856) and source paths (968), file-granular, untrusted [A §1.2].
- **AC to ADR:** only `doc_links[]` (about 40 relationship spellings) and prose [A §1.2].
- **ADR/Doc to Component:** `components[]`, enforced. ADR/Doc to anything: `related_docs[]`, untyped.
- **Ticket:** to AC via `ac_traceability.id`, `source_ac` and a `depends_on` that holds AC ids; to File via `files_touched[]` [A §1.10].
- **Component to code:** `primary_code[]`, usually directories. AC to Phase: `roadmap_phase` (about 48 % set).
- **Absent:** Policy, Workflow and (on main) Capability links; Test to Function; AC to Function; Component to AC by file location [A §3].

Trust ratings per edge: `docs/reference/artifact-knowledge-graph-data-map.md`.

### Q4. Which abstractions should Neo4j index rather than replace?

**Index (read-only compile):**
- the `knowledge_query` nodes and edges (identity and edge backbone);
- `get_ac_index` in `scripts/commit_guardian/_ac_store_index.py` L234 (AC properties);
- `docs/components.json`, ADR frontmatter plus a new heading parse, `docs/roadmap.json`, ticket frontmatter;
- the `# covers:` tag scan.

**Do not replace:**
- the AC store and its hooks;
- `knowledge_query` and its consumers (visualiser, the K `knowledge_map` bridge);
- `GapStorePort`, the run root and the checkpointer;
- Langfuse, the glossary flow and the knowledge-emission pipeline.

Sources: B §1.4, §2.3.

### Q5. What is the smallest projection that demonstrates value?

- Declared Component, AC, ADR (with Section), File, Ticket, Phase and Test-as-file, plus learned Decision: about 4.5k ACs and 33k edges, rebuilt in seconds.
- Value is shown when five registered queries answer the live-QA misses (rows 6-11) and the missing decision write-back (row 19) by query instead of by sampling 20 of about 4,460 files [B §4].
- Detail: [part 2 §(c)](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md).

### Q6. Which existing agent or capability owns each artifact update?

- **product-owner:** vision, mission and roadmap, plus L0/L1 ACs.
- **business-analyst:** L2/L3 ACs. **it-po:** technical enrichment and the test contract.
- **documentation-expert:** routes ADRs to adr-author and diagrams to architecture-diagram-author.
- **Glossary:** the `check-glossary-coverage` hook.
- **No owner today:** product principles and a concept-level QA matrix.
- Table: [part 3 §(f)](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md) [C §1].

### Q7. What conflicts with the current design?

| Conflict | Where | Resolution path |
|---|---|---|
| Store technology: Neo4j vs Postgres | ADR-057 §2, §6 (BOOT, MUST be relational) | Decisions 1 and 2 |
| Ids: `ac:x:y` vs `PREFIX-NNN` (ADR-008) | Concept §10, §11 | Project existing ids (ADR-061) |
| AC colocation beside code | Concept §10 vs the central store by namespace; "Git-native" holds as same repo, same PR | Accept the central store [A §1.2] |
| Authority of learned records | Concept §7 vs `colony-memory.md` "derived, never workflow state" | Decision 4 |
| A file-backed Mode 0 | ADR-057 Alternatives reject local files; lesson summary says "files now, graph later" | Decision 5 |
| Four stage-numbering schemes | Concept 0-7, spec 0-5, kernel and colony roadmap phases | Decision 6 |
| L0 AC format and level | Concept `L0-AC-01` vs `PREFIX-NNN` and PO language; the kernel ticket is AC-free | Decision 3 |
| Precedent retrieval vs "no routing influence before calibration" | ADR-056 §9, ADR-057 §10 | Decision 8 |
| Managed Mode 2 | Not in vision or roadmap | PO decision, deferred |
| Concept lacks approval provenance, per-stage colony-health measures (ADR-056 §9), held-out evaluation before routing influence (spec §19.4) | Lesson 16; C §2f | Add to ADR-059/060 and stage exits |

Vision and mission agree in substance; only the middle layer conflicts [C §2a].

### Q8. Which ADRs need creating versus updating?

Create ADR-059 (A, folding F and I), ADR-060 (B) and ADR-061 (E). C and D are covered by ADR-053 and ADR-054. Amend ADR-056 (G, the H open items, Postgres pointers) and ADR-058 §6. Detail: [part 3 §(e)](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md) [C §3].

### Q9. What is the smallest migration path from the Postgres concept?

Nothing was ever written to Postgres and no code exists, so this is a document migration followed by store-agnostic code [B §3.5]:
1. **Docs:** ADR-059 supersedes ADR-057's store choice; amend ADR-056 and ADR-058 pointers; update `colony-memory.md`, vision, roadmap and four diagrams (BOOT).
2. **Store-agnostic code:** `kernel/memory/` port, `NullColonyMemory` and startup selection. This step serves either backend.
3. **`Neo4jColonyMemory`:** lazy driver import, constraints, `SecretSettings` fields.
4. **Ingester:** the declared-graph ingester as a separate trusted CLI.
5. **Read and write paths:** the `graph_query` source with the registered queries, then `DecisionRecord` writes at approval and finalize.

### Q10. What does the final Neo4j MVP look like?

See [part 2 §(c)](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md): nodes and edges, the five queries mapped to lesson rows, ingestion prerequisites, Mode 0 behaviour and the explicit non-goals.
