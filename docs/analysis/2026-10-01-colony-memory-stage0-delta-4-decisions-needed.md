---
title: "Colony Memory Stage 0 Delta Design - Part 4 of 4"
description: "Stage 0 delta design for the Neo4j colony memory concept, part 4 of 4: the eight decisions needed from the user before any ADR or code (ADR-057 supersede vs amend, Neo4j instead of or beside Postgres, L0 ACs, learned-knowledge authority, Mode 0, stage numbering, knowledge_query fixes, precedent vs routing), each with options and a recommendation, plus the defaults assumed otherwise."
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

> Part 4 of 4 of the Colony Memory Stage 0 delta design ([previous part](2026-10-01-colony-memory-stage0-delta-3-lessons-adrs-ownership.md) | last part). Evidence tags are defined in [part 1](2026-10-01-colony-memory-stage0-delta.md#evidence-legend).

## (g) Decisions needed from the user

| # | Decision | Recommendation |
|---|---|---|
| 1 | ADR-057: supersede via ADR-059, or amend in place | Supersede in part via ADR-059; land ADR-057 as written first |
| 2 | Neo4j instead of Postgres, or alongside it | Instead |
| 3 | The concept's L0 ACs: real ACs via `/plan-feature`, or roadmap exit criteria | Exit criteria now; invariants into ADRs; real L0/L1 via `/plan-feature` when the Stage 1 build is scheduled |
| 4 | Authority of learned knowledge | Approved records are authoritative in memory and must be exportable; statistics stay derived; neither is ever workflow state |
| 5 | Mode 0: Null only, or a local `FileColonyMemory` | Null only for Stage 1; keep the port file-implementable |
| 6 | One stage-numbering scheme | Roadmap phase ids are the only scheme; concept stages map onto them |
| 7 | Are the `knowledge_query` fixes in Stage 1 scope? | Yes, as the first Stage 1 tickets, separate from Neo4j |
| 8 | Precedent as evidence vs "routing influence" | Precedent as cited evidence from Stage 1; routing influence stays gated |

### 1. Supersede ADR-057 via ADR-059, or amend it in place

**Situation.** ADR-057 is Accepted but uncommitted in BOOT, where another session is still editing. Its §2 and §6 are MUSTs for PostgreSQL and relational tables [C §0, §2f].

**Options:**
- (a) Land ADR-057 as written, then ADR-059 supersedes it in part.
- (b) Rewrite ADR-057 in place before it lands.

**Recommendation: (a).**
- A new file does not collide with the other session's work in BOOT.
- It keeps the 2026-09-30 reasoning. ADR-057's Alternatives never considered a graph database, so the concept's argument is new evidence, which is what supersession records.
- The carried rules (§3, §5, §7, §9, §10) stay citable at stable section numbers.
- `docs/how-to/documentation/write-adr.md` treats a reversal as a new ADR with Supersedes.

**Cost.** One more ADR and a status flip on ADR-057. Choose (b) only if you want fewer documents; then record Postgres under Alternatives so the history is not lost.

### 2. Neo4j instead of Postgres, or alongside it

**Options:**
- (a) Neo4j instead: one optional store.
- (b) Neo4j for the graph and precedents, Postgres for counters (`capability_stats`, `path_stats`).

**Recommendation: (a).**
- No code exists for either store.
- Counters are concept Stage 4 work. There they become Capability properties or small nodes (concept §24), with Langfuse as the analytics warehouse.
- Two stores would double the Mode 1 setup, secrets, migrations and the shared-store privacy question (ADR-057 Open Question 1).

**Revisit when** Stage 4 statistics prove too heavy for the graph.

### 3. The concept's L0 ACs: real ACs via /plan-feature, or roadmap exit criteria

**Mapping.** Leafcutter levels are L0 portfolio goal, L1 feature benefit, L2 Gherkin behaviour and L3 edge case (`docs/reference/ac-schema.md`). Ids are `PREFIX-NNN` (ADR-008) under a namespace in `docs/acceptance-criteria/index.yaml`, so the concept's `L0-AC-01` would become, for example, `CM-100` in a new colony-memory namespace. Of the concept's fifteen [C §2c]:
- 01 and 05 are already true (ADR-010).
- 02, 14 and 15 are architecture invariants, not customer value, so the PO would rewrite or reject them.
- 03, 04, 06, 07 and 08 are L1-sized.
- 09-13 belong to concept Stages 2-5.

**Recommendation:**
1. **Now:** keep them as exit criteria on the colony and kernel roadmap phases, as `phase_colony_*` does today. This is consistent with the AC-free kernel ticket.
2. **Into ADRs:** put 02, 14, 15 and approval provenance into ADR-059/060 as MUST rules.
3. **At build time:** when the Stage 1 build is scheduled, run `/plan-feature` for one or two real L0s in customer language, for example "a decision approved once is offered the next time that kind of decision comes up" and "Leafcutter behaves the same with no memory store". Their L1s come from 03, 04, 06, 07 and 08.

**Prerequisites.** This needs a `colony_memory` component and an AC namespace on main.

### 4. Authority of learned knowledge

**The conflict.** Concept §7 says learned knowledge "may initially live only in Neo4j". `colony-memory.md` (BOOT) says the store is "derived, never workflow state", recomputable from Langfuse and run roots [B §3.4 (1)].

**Recommendation: split by record type.**
- **Approved records are authoritative in memory.** Human-approved Decision records (later Lessons) are authoritative there until promoted to Git. They therefore need an export and restore path (a JSONL dump through the port), so losing Neo4j is survivable. L0-AC-02 then reads: declared nodes are rebuildable from Git; learned records are exportable.
- **Statistics stay derived.** Counters, path statistics and outcome aggregates are rebuildable from Langfuse and run records.
- **Never workflow state.** Neither kind is workflow state: the run root and the checkpointer stay authoritative for a run (ADR-057 §9).

### 5. Mode 0: Null only, or a minimal local FileColonyMemory

**The tension.**
- Concept §25 and ADR-057 §3 say Mode 0 means learning off.
- ADR-057's Alternatives reject "SQLite or local files only" because a team cannot share them.
- The lessons summary (L §2) suggested "files now, a graph later".

**Recommendation: Null only for Stage 1.**
- Define the port so that a file-backed implementation remains possible: approved decisions and gaps only, JSONL under the run root, no declared-graph queries.
- An in-memory double for tests is needed either way.

**Cost.** Lesson 19 is fixed only for users who run Neo4j. If you want decision memory in every install (the phase_1 outcome is "installs into any project"), choose the file store instead. ADR-059 must then rescope ADR-057's rejection to "not sufficient for shared learning".

### 6. One stage-numbering scheme

**The schemes.** Concept 0-7; kernel spec Rev 3 0-5; the BOOT roadmap with `phase_kernel_1..5` and `phase_colony_1..5`; main with neither [C §2b].

**Recommendation.** The `docs/roadmap.json` phase ids are the only scheme: they are schema-checked and used by AC and ticket `roadmap_phase`. Concept stages are cited as "concept Stage N" through this mapping, never as new ids. Concept "Stage 0" is this delta design, which is unrelated to spec Stage 0.

| Concept stage | Roadmap phase (BOOT ids) | Note |
|---|---|---|
| 1 Declared graph and `graph_query` | `phase_kernel_2_knowledge` | Spec Stage 2 "knowledge and context compiler"; spec part 7 §21 leaves Neo4j vs relational open |
| 1 Port, Decision and Gap writes | `phase_colony_1_collect` | Retitle: "optional Neo4j store" instead of "optional PostgreSQL store" |
| 2 Memory capture (Mistake, Lesson) | `phase_colony_2_analyze` | Mistake and Lesson nodes are new to ADR-056/057 |
| 3 Semantic precedent | `phase_colony_3_suggest` | "Evidence shown, routing unchanged" fits exactly |
| 4 Colony reinforcement | `phase_colony_2_analyze` to `phase_colony_4_influence` | Same gating as ADR-056 §9 |
| 5 Crystallisation | `phase_colony_5_evolve` | |
| 6 Proposed-knowledge overlays, 7 Managed memory | none | New phases only if the PO accepts them |

**Simpler alternative.** Put all of concept Stage 1 under `phase_colony_1_collect`, retitled "COLLECT and READ".

### 7. Are the knowledge_query defects in Stage 1 scope?

**The defects** (part 2 §c.3, items 1-4): double-indexing, id collisions, kebab/snake twins, overloaded edge types.

**Recommendation: yes, as the first Stage 1 tickets, independent of Neo4j.**
- The fixes help the existing map, the kernel `knowledge_map` bridge and the visualiser even in Mode 0.
- Without them the ingester must compensate with its own identity mapping, which is the second id system L0-AC-15 forbids.

**Constraint.** `scripts/knowledge_query.py` is 1,794 lines, over the 400-line limit, and may not grow, so the fixes extract into sibling modules. The status-axis choice and the property join belong in the exporter, not in `knowledge_query`.

### 8. Precedent as evidence vs "routing influence" (ADR-056 staging)

**The question.** ADR-056 §9 and ADR-057 §10 forbid historical data from influencing routing before calibration and the spec §19.4 held-out evaluation. Concept §15 and §29-E retrieve past decisions during a decision [B §3.4 (4)].

**Recommendation: allow precedent as cited evidence from concept Stage 1.**
- **What enters.** Approved records only, labelled with age, repository revision and any supersession or correction. A precedent enters the decision as evidence with provenance.
- **What it never changes.** Capability routing, eligibility or Jev thresholds. Routing influence stays behind the ADR-056 §9 health measures and the §19.4 evaluation.
- **Where it is written.** ADR-059 must say this explicitly and add a stage-table row, "READ: declared graph and approved precedents as evidence", or reviewers will read precedent retrieval as a staging violation.
- **Anchoring risk.** Mitigate it by returning corrected and superseded precedents alongside, and by requiring the decision to say whether the precedent's context still holds (concept §22).

## Defaults assumed unless you object

- ADR identity is the integer `ADR-NNN`, not the filename stem [A OQ2].
- Stage 1 test links are file-level. Function-level links come later, using the enclosing-function logic in `scripts/ac_store/done_proof.py` [A OQ8].
- Neo4j is read through the port (`run_registered_query`), not through a second driver handle [B OQ4].
- Query parameters come from a deterministic resolver (`Scope.component_ids`, extracted terms, need category); no `retrieval_request.v2` yet [B OQ3].
- The ingester is a sibling exporter module plus a trusted CLI, run on merge to main [B OQ1].
- `repository_id` is user-configured, falling back to the normalised git remote URL; ADR-061 decides [A OQ6; ADR-057 OQ5].
- Sections are Markdown headings with numbered anchors, because ADR text cites "§9" [B OQ6].
- Environment variables: `LEAFCUTTER_NEO4J_URI`, `LEAFCUTTER_NEO4J_USERNAME` and `LEAFCUTTER_NEO4J_PASSWORD` in `SecretSettings`, which reports presence booleans only. `LEAFCUTTER_SELF_LEARNING=false` stays the opt-out.
- The Neo4j driver is an optional, lazily imported extra. The kernel stays leafcutter-ai only, as in kernel V0.

## What Stage 0 deliberately did not do

- No Neo4j schema, constraint or index is finalised (concept §29).
- No ADR is written: the plan in part 3 waits on decisions 1, 2, 4 and 8.
- No code, config, roadmap, vision, AC or glossary change.
- The BOOT worktree was read only.
