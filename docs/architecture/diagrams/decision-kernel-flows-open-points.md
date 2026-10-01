---
title: "Decision Kernel and Colony Memory — Open Points in the Designs"
description: "Numbered list of the places where the Decision Kernel, colony memory and legacy-pipeline sources are silent, disagree with each other, or disagree with the code on the kernel branch, each with the exact sources involved. Nothing here is resolved; the flow and context pages point to these items instead of choosing an answer."
type: reference
flight_level: L3-Component
diagram_type: none
status: draft
parent: docs/architecture/diagrams/decision-kernel-flows-overview.md
created: 2026-09-30
last_updated: 2026-09-30
source_ticket: null
components:
  - decision_kernel
related_docs:
  - docs/architecture/diagrams/decision-kernel-flows-overview.md
  - docs/architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md
  - docs/architecture/adrs/ADR-055-capability-registry-starts-empty.md
  - docs/architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md
  - docs/architecture/adrs/ADR-057-colony-memory-store-optional-postgres.md
  - docs/architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md
  - docs/analysis/2026-09-30-decision-kernel-design-4-jev-and-capabilities.md
tags:
  - decision-kernel
  - colony-memory
  - open-questions
---

# Decision Kernel and Colony Memory — Open Points in the Designs

The pages under the [Design Map](decision-kernel-flows-overview.md) map only what the sources
say. This list names every place where they are silent or disagree, found while writing those
pages on 2026-09-30. Some items are drift between the design text and the code on
`feature/kernel-bootstrap-v0`. None is resolved here.

## A. Context and capabilities

- **OP-01 Routing state: design and code differ.** Design part 4 sends
  `{"request": {kind, goal, question, payload_summary}, "task": {goal, component_ids}}`. The P4
  code (`kernel/scheduler/routing.py`) sends `task` plus `requests.<work_item_id>` with `kind`,
  `goal`, `question`, `payload_schema`, `payload_keys` and `clarifications`. The code's decision
  history explains the batching; the design text is not updated yet.
- **OP-02 The clarification return path exists only in code.** Design part 4 says
  `insufficient_context` creates a human clarification request. It does not say how the answer
  is used. P4 code (`nodes_route.py`) feeds the answers back into the routing state.
- **OP-03 How colony statistics enter routing is not designed.** The source puts it as
  "semantic suitability + historical evidence + cost + latency + failure/rework rate → Jev →
  choose path"; [colony-memory](../components/colony-memory.md) says the kernel passes statistics
  "to Jev as routing context". Not stated: which fields, whether they go into the state or the
  criterion text, the new template version, and whether Jev or code weighs statistics against
  semantic fit (ADR-053 §5 keeps exact computation in code).
- **OP-04 Criteria edits: the design says open, the code decides.** Design part 4 lists "how an
  edit is expressed" as open for P5/P6. P5 code (`kernel/capabilities/decision/approvals.py`)
  turns each non-empty line of `free_text` into a required criterion that replaces the pending
  proposals.
- **OP-05 The glossary is not a V0 retrieval source.** Design part 1 calls glossary and
  components "knowledge-map surfaces for retrieval. Deeper use is Stage 2." `config/paths.json`
  has a `glossary` surface, but no default kernel source includes it. Spec §17.1 puts
  glossary-aware context in Stage 2.
- **OP-06 No source-authority order.** Spec §21 asks for "minimal explicit rules for MVP". The V0
  design records conflicts and escalates them, but defines no precedence between sources (for
  example an ADR against `CLAUDE.md`).
- **OP-07 Policies have no runtime home.** ADR-054 level 2 has no V0 mechanism, spec §4.3
  excludes a policy engine from the MVP, and storage and format are undecided (ADR-054 open
  question 2). Component-scoped policies are Stage 3 (spec §18.4).
- **OP-08 The invocation compiler has no place yet.** ADR-052 §3 requires it and leaves open
  where it lives in `kernel/`. The V0 design parts never mention it. V0 builds Jev questions
  from versioned templates and host packets in `open_interactions`. No source says whether these
  are the compiler's first form or whether a separate compiler follows.
- **OP-09 Lifecycle transitions are unspecified.** ADR-052 §4 names steps and outcomes, but not
  which check leads to which outcome, where REPAIR re-enters, or whether `needs_human` is
  REQUEST INFORMATION or ESCALATE. ADR-052 also leaves open whether the V0 graphs are restated
  in lifecycle terms.
- **OP-10 No executor for a coding worker before Stage 5.** Stage 3 defines coding and testing
  views (spec §18.3), and Stage 5 adds direct coding executors (spec §20). No source says whether
  a Stage 3 worker runs as a Claude Code handoff, where every V0 host operation forbids
  `edit_repository`, or waits for Stage 5.
- **OP-11 ADR-055's wording against retrieval.** ADR-055 §2: the kernel "MUST NOT read,
  normalize or route over the legacy agent, skill, workflow or command registries". The V0
  source `knowledge.components` reads the knowledge-map surfaces `agents` and `skills`, which
  `config/paths.json` maps to `config/agent_registry.json` and `config/skill_registry.json`, as
  evidence. ADR-055's context is routing; its wording also forbids reading.
- **OP-12 The host LLM's ambient context.** In V0 the host is a Claude Code session, so
  `CLAUDE.md`, auto-memory, skills and MCP prompts reach it next to the kernel packet. Spec §2.3
  and §11.5 name this; spec §20 brings fresh per-task context in Stage 5. No source says how
  ADR-052's compiled-instructions rule applies to host work until then, or whether the kernel
  should record which ambient context was present.

## B. The legacy pipeline

- **OP-13 Injection builder: doc and code differ.** `docs/architecture/components/injection-builder.md`
  says supervisors invoke it before spawning a phase agent and gather all 11 channels. The
  docstring of `scripts/injection_builders.py` says it builds tables injected into compiled
  agent templates at build time and exposes `assemble_context_bundle` for the fast lane.
- **OP-14 Two legacy topology docs disagree.** `docs/agentic-runtime-flow.md` still draws
  epic-supervisor → ticket-supervisor → phase agents. `docs/architecture/agent_delivery_workflows.md`
  §4 records the ADR-019 correction: `build-feature.js` dispatches phase agents directly at
  depth 1. The design map follows the second.
- **OP-15 The skill name — settled.** Spec §11.1 names the skill `/leafcutter`, which is already
  the shipped knowledge-hub command. The user decided (2026-09-30): the kernel skill is
  `/leafcutter`, and the knowledge-hub command is renamed in its own ticket and branch
  (`chore/rename-leafcutter-hub-command`).
- **OP-16 The legacy pipeline's future.** ADR-052 and ADR-055 say both coexist, and the kernel
  is not shipped to adopters. ADR-052's "migrate one agent prompt and compare" is proposed, not
  decided. No source says whether or when legacy agents retire, whether the kernel will ship to
  adopters, or which legacy assets are candidates for `legacy_admission`.

## C. Colony memory and learning

- **OP-17 Whether COLLECT starts inside V0.** ADR-057 §10: earliest right after V0; starting it
  inside V0 "is a decision for the V0 build". The roadmap's founding exit criteria need the
  ADR-056 §9 recording prerequisites implemented or explicitly deferred. Neither is recorded.
- **OP-18 Two roadmap tracks describe one store.** `phase_kernel_4_trails` still says an
  analytics job "feeds a performance store". The new `phase_colony_1_collect` to
  `phase_colony_5_evolve` (roadmap as edited on 2026-09-30) use ADR-057's names. How the two
  tracks' exit criteria relate is not stated.
- **OP-19 The learning evaluator.** Cadence, placement and inputs are open (ADR-057 open question
  4), including whether it reads the local `events.jsonl` (ADR-056 open question 5). Degraded
  runs are never re-exported, so an evaluator that reads only Langfuse undercounts them.
- **OP-20 Local gap records and the store.** `gaps/observations.jsonl` stays the V0 gap record;
  ADR-057 §6 makes `capability_gaps` its cross-run counterpart. How local observations reach the
  store is not stated.
- **OP-21 Scores and datasets.** ADR-058 decides them but "does not schedule" them; the roadmap's
  `phase_colony_2_analyze` now lists them among its exit criteria. Still open: score names and
  owners, sampling and retention, where scores are written (ADR-058 open questions 1–3), and
  whether ADR-056 §9's outcome event keyed to `decision_id` is a Langfuse score, a local
  `RunEvent`, or both.
- **OP-22 Context dimensions have no V0 fields.** ADR-057 §7 requires capability, task_type,
  component, repository/project and policy_version on every statistic. V0 has no `task_type` or
  decision-type field (ADR-056 open question 4), and repository identity across clones is open
  (ADR-057 open question 5).
- **OP-23 A configured store that cannot be reached.** ADR-057 open question 6; the source is
  silent.
- **OP-24 Held-out cases.** Spec §19.4 requires held-out evaluation, and ADR-058 notes that a
  case that motivated a change is not held out for it. How held-out cases are chosen is not
  stated.
- **OP-25 Further open questions carried from the ADRs.** Ground truth for "correct", the decay
  function, the exploration rate and automatic threshold changes (ADR-056 open questions 3, 1, 2,
  6); privacy for a shared store, migrations, retention and the calibration bar for INFLUENCE
  ROUTING (ADR-057 open questions 1, 2, 3, 7).

## Settled while this map was written

- The colony store's stages: ADR-057 §10 and the roadmap's `phase_colony_*` phases.
- The configuration names `LEAFCUTTER_COLONY_DB_URL` and `LEAFCUTTER_SELF_LEARNING` (ADR-057 §4).
- ADR-056's "performance store" is ADR-057's "colony memory store" (ADR-057 §1). The glossary
  entry "performance store" still uses the older name; it was not edited here.
- `host.research` is `fixed` with operation `bounded_research` in both design part 2 ("as
  built") and `config/capability_registry.json`.

## Cross-Links

- Parent: [Design Map](decision-kernel-flows-overview.md)
- Open questions at their source: [ADR-052](../adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md),
  [ADR-054](../adrs/ADR-054-process-representation-and-maturity-model.md),
  [ADR-056](../adrs/ADR-056-colony-memory-evidence-reinforcement.md),
  [ADR-057](../adrs/ADR-057-colony-memory-store-optional-postgres.md),
  [ADR-058](../adrs/ADR-058-langfuse-colony-history-scores-datasets.md),
  [design part 6 risks](../../analysis/2026-09-30-decision-kernel-design-6-tests-phases-risks.md)
