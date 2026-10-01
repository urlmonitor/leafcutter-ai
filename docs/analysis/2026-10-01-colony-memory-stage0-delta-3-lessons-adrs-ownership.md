---
title: "Colony Memory Stage 0 Delta Design - Part 3 of 4"
description: "Stage 0 delta design for the Neo4j colony memory concept, part 3 of 4: the 19 kernel V0 live-QA lessons mapped to concept sections and MVP items, the approval-provenance gap, the ADR plan (ADR-059 to ADR-061, amendments, stale artifacts) and the artifact ownership and propagation plan."
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

> Part 3 of 4 of the Colony Memory Stage 0 delta design ([previous part](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md) | [next part](2026-10-01-colony-memory-stage0-delta-4-decisions-needed.md)). Evidence tags are defined in [part 1](2026-10-01-colony-memory-stage0-delta.md#evidence-legend).

## (d) Live-QA lessons mapped to the concept

Rows are from L §1 (kernel V0 live QA, 2026-10-01). "MVP item" refers to [part 2](2026-10-01-colony-memory-stage0-delta-2-reuse-and-mvp.md).

| # | Lesson (short) | Concept section | MVP item | Status after the MVP |
|---|---|---|---|---|
| 1 | Every goal forced to `decision_report` | §5 placement ladder; §14 "the model decides what it needs" | none | Fixed in V0 (intake intent); outside the concept |
| 2 | "Weather" logged as a build opportunity | §23 gaps as scouts | Gap sink keeps the gap type (`out_of_domain` is not a scout) | Fixed in V0 |
| 3 | Write-vs-read; the clarification answer could not re-drive routing | none | none | Fixed in V0; still open in the concept |
| 4 | Descriptor wording is routing data | §9.1 Capability; §24 | none (Capability deferred) | Fixed in V0 |
| 5 | Options generated without research, from the kernel's own list | §14; §16 action-scoped memory | Q-A as the option basis | Fixed (grounding); Q-A makes the basis structured |
| 6 | Tests, config, AC store, roadmap, tickets not searched | §13; §14 | Q-A, Q-B | Fixed (sources); the graph makes it structural |
| 7 | Design and component docs invisible | §9.1 Document / ArchitectureArtifact | Q-B; Q-C once Section covers `docs/analysis` | Partly: the MVP covers ADR sections only |
| 8 | AC store sampled 20 of about 4,460 by wording | §10; §13 | Q-A | Fixed by the MVP (ticket StructuredStoreQuery) |
| 9 | Aspirational docs marked a need "satisfied" | none (§20 is about outcomes, not evidence) | Q-D | Partly: Q-D is a signal; the judgement stays with ticket AnswerAwareCoverage |
| 10 | One 25-line window per file; ADR-057 §9 missed | §13 | Q-C, Section nodes | Fixed for ADRs; ticket SectionAwareRetrieval covers plain text |
| 11 | Lexical prefilter dropped `kernel/persistence/*` | §13; §16 | Q-B with `primary_code` expansion | Fixed when directories are expanded |
| 12 | Sizing: native evidence vs an LLM | §5 ladder | none | Fixed in V0; outside the concept |
| 13 | Host findings dropped (plumbing) | none | none | Fixed in V0; not applicable |
| 14 | Caller-named options ignored | §15 decision options | `DecisionRecord.options[].proposed_by`, `named_in_goal` | Round 5; the MVP keeps option provenance |
| 15 | Scoped repo's `scripts/` executed; `git status` could write its index | §8 ingestion; §25 | Ingester and adapter run from the trusted installation; scoped repo is data only | Round 5; an MVP rule |
| 16 | Policy commit refused for instruction poisoning | **none: concept gap** | Q-E approved-only; approval fields on `DecisionRecord` | Still open in the concept; rules below |
| 17 | Build-phase engineering defects | none | none | Fixed in V0; not applicable |
| 18 | Uncalibrated thresholds | §19-20; §30 Stage 4 | none | Still open (Stage 4; ADR-056) |
| 19 | The kernel writes no decision back | §15; §17; §29-E | `ColonyMemory`, `DecisionRecord`, Q-E | Fixed by the MVP |

### The gap the lessons expose: approval provenance

Lesson 16 and the refused commit of the seed policy POL-GIT-001 show the risk. An agent tried to take skip-confirmation authority from a policy file it had just written, and the commit was refused as instruction poisoning. The concept's §7 promotion path and §15 precedent memory have no rule against this. Proposed rules for ADR-060 (or ADR-059):

1. **Records start as proposals.** A learned record is written `approval_status = proposed` unless a human approval event exists for it: the `approvals.py` approval with its `approved_by` actor.
2. **Only approved records count as precedent.** Q-E returns `approved` records only. A proposed record is never shown as authority; in the MVP it is not returned at all.
3. **Nothing derives authority from a model-written record.** An approval must point to an approval event recorded outside the record's own text: actor, time, run id and trace id. A record cannot cite itself, or another model-written record from the same run, as its approval basis.
4. **Promotion takes authority from the merge.** Promotion to Git (concept §7) goes through a PR and human review. The re-ingested artifact takes its authority from that merge, never from the memory record.
5. **Supersession keeps the original.** A correction keeps the original record (concept §22) and needs the same approval level as the original.

If L0 ACs are authored (decision 3), this becomes one of them: "A learned record cannot authorise itself."

## (e) ADR plan

**Numbering** [C §0]:
- Main stops at ADR-050 (045 is missing).
- ADR-051 exists only on `epic/every-piece-of-separate-work-gets-its-workspace`.
- ADR-052..056 are in PR #973; ADR-057/058 exist only in BOOT, uncommitted.
- The next free number is **ADR-059**. The collision hook (ADR-029) sees one tree, so reserve 059-061 now (062/063 if F or I split out).

| Candidate | Action | ADR | Content |
|---|---|---|---|
| A backend | CREATE | **ADR-059** "Colony memory store is a graph (Neo4j) behind `ColonyMemory`" | Supersedes ADR-057 §1, §2, the §3 implementation list, the §4 variable names, §6 and the Postgres Alternatives. Restates the carried rules by reference (part 2, row 14). Adds the read side (`graph_query`, registered queries, staleness). States precedent-as-evidence (decision 8) and the unreachable-store behaviour. **Folds F:** main-merge boundary, trusted ingester, provenance, exclusions. **Folds I:** Null, Neo4j (self-managed or Aura), managed service later. If decision 1 is "amend in place", this text becomes ADR-057 revision 2 and 059 stays free. |
| B source of truth | CREATE | **ADR-060** (or fold into 059) | Declared knowledge is canonical in Git; the compiled graph is derived, read-only and rebuildable; learned records follow decision 4; execution stays in Langfuse; the approval-provenance rules above. Companion to ADR-034/040 (knowledge-write ownership). |
| C Det / Jev / LLM / Human | COVERED | ADR-053 | No new ADR. |
| D workflow / policy / LLM | COVERED | ADR-054 | No new ADR. |
| E ids | CREATE | **ADR-061** (small) | Project existing ids; key (repository_id, kind, id). Learned ids use the kernel `ID_PATTERN` prefixes. Settles the `repository_id` source (ADR-057 Open Question 5) and the ADR integer vs filename-stem form. Drops `ac:x:y`. |
| F ingestion | FOLD | into ADR-059 | Split out as ADR-062 only if ingestion grows a CI service. |
| G lifecycle | AMEND | ADR-056 §7 (and/or ADR-054 §2-3) | Add the pre-policy tiers (Observation, Memory, Mistake, Lesson) and promotion through a PR. |
| H reinforcement safety | MOSTLY COVERED | ADR-056 §2-4, §9 | Open items: multi-horizon outcomes (concept §20) are not in ADR-056; decay is its Open Question 1; ground truth is Open Question 3. Amend only when the user wants them settled. |
| I backend abstraction | FOLD | into ADR-059 | The managed tenant service gets its own ADR (ADR-063) when concept Stage 7 is on the roadmap. |

**Amendments:**
- ADR-056: `related_docs`, the §9 closing paragraph and Open Question 5 (Postgres mentions), §7 (candidate G).
- ADR-058: the §6 three-layer table (store pointer to Neo4j).
- ADR-057: status superseded-in-part. Frontmatter and body change together (`docs/how-to/documentation/write-adr.md`).
- `docs/architecture/adrs/README.md`: regenerate with `python scripts/adr_refs.py --index --write`.

**Artifacts that go stale.** All are in BOOT and uncommitted; grep counts from C §2e:
- `docs/vision.md` (3);
- `docs/roadmap.json` (4) and `docs/roadmap.md` (5, a regenerated mirror): the `phase_colony_*` titles and the `phase_kernel_4_trails` text;
- `docs/components.json` (`colony_memory` description);
- `docs/architecture/components/colony-memory.md` (23) and `decision-kernel.md` (2);
- four diagrams: `decision-kernel-flows-learning-loop.md` (6), `-flows-overview.md` (4), `-flows-open-points.md` (2), `-context-jev.md` (2).

**Order:**
1. Decisions 1, 2, 4 and 8.
2. PR #973 (ADR-052..056) and the BOOT ADR-057/058 land.
3. ADR-059, then ADR-060/061.
4. The amendments.
5. Propagation (§(f)).

## (f) Ownership and propagation plan (concept §33)

Owners are the agents registered today [C §1]. Every edit below needs its own ticket (CLAUDE.md ticket mandate); this Stage 0 ticket covers only this docs commit.

| Concept §33 artifact | Owner | Route | Note |
|---|---|---|---|
| Vision, mission, product principles | product-owner | `/po` or `/plan-feature` (strategic): shows a diff, applies only after explicit user confirmation, and creates an L0 AC alongside | Product principles have no artifact today; recommend a section of `docs/vision.md` |
| Roadmap, capability roadmap, MVP scope and non-goals, managed-memory option | product-owner | `/po`; `roadmap.md` is regenerated by a hook; `roadmap-steward` audits read-only | Stage mapping is decision 6; the managed option needs a PO decision |
| L0/L1 ACs (concept §31) | product-owner | `/plan-feature` (ac-triage, then PO, then a user gate) | Decision 3. Needs a colony AC namespace in `docs/acceptance-criteria/index.yaml` and the component in `docs/components.json` |
| L2/L3 ACs | business-analyst | `/ba` or `/plan-feature` stage 2 | Gherkin AC YAML |
| Technical enrichment and the test contract (§33 QA list) | it-po | `/it-po` or `/plan-feature` stage 3 | No test-planner owner; the standing strategy is `docs/testing/test-angles.md` |
| ADR-059..061 and the amendments | documentation-expert, then adr-author | `/documentation` (decide-record) or the ticket phase | adr-author picks the number: reserve 059-061 first |
| Architecture docs: `colony-memory.md`, graph schema, ingestion architecture, backend abstraction | documentation-expert, then architecture-diagram-author, explanation-author, reference-author | `/documentation` | `documentation-expert.md` line 9 names `architecture-author`, which does not exist (the real agent is `architecture-diagram-author`). Fix by its own ticket |
| Diagrams (the five in §33) | architecture-diagram-author (skill `write-c4-diagram`) | via documentation-expert or ticket phase | Update the four stale BOOT diagrams first |
| Setup docs: optional Neo4j configuration, self-hosted vs managed | documentation-expert, then how-to-author and reference-author | `/documentation` | After ADR-059 |
| Terminology | glossary-triage, driven by the `check-glossary-coverage` hook | automatic at commit | Never hand-edit the glossary |
| Component registry (`colony_memory`, ingester component) | `add-component` skill or documentation-expert | `/add-component` | BOOT already registers `colony_memory` (planned) |
| Kernel port, `graph_query`, `DecisionRecord`, ingester code | Ticket-driven build (test-writer, python-coder) | Tickets from `/plan-feature` and `/build-ac`, or an umbrella ticket (decision 3) | Kernel capabilities cannot dispatch PO, BA or adr-author (ADR-055) |
