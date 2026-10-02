---
title: "leafcutter-ai Vision"
description: "Product vision — what leafcutter-ai is, who it serves, the outcomes it delivers, and the colony model it grows toward"
type: cross-cutting
status: active
created: 2026-05-19
last_updated: 2026-09-30
components:
  - documentation_system
  - decision_kernel
tags:
  - vision
  - roadmap
  - colony-memory
build_behavior: write_if_absent
---

# leafcutter-ai Vision

## Mission Statement

leafcutter-ai makes AI-assisted software development disciplined in any codebase, and over time learns from observed outcomes which engineering processes and decisions actually work.

Today it is delivered as a domain-agnostic agent/skill/workflow package that installs a full AI-assisted development workflow into any project. Edit one JSON config file, run `build.py`, and the complete system is generated: agents, skills, hooks, ticket lifecycle, documentation scaffolds, and quality gates. The goal is to make AI IDEs and agents (Claude Code, Antigravity, etc.) productive and disciplined in any codebase without requiring project-specific prompt engineering.

Its long-term core is the Decision Kernel: a runtime that works like a leafcutter colony. It starts small and leans on a general-purpose model, and it grows stronger with every task it resolves.

## Why "Leafcutter": The Colony Model

Leafcutter ants have no central planner. They coordinate through *stigmergy*: foragers that find food lay pheromone on the way back, other ants follow the strongest trails, and trails that stop paying off evaporate. The colony gets better at foraging without anyone directing it. Leafcutters also don't eat the leaves they carry. They grow a fungus garden on them and live from the garden.

Leafcutter works the same way:

| Ant colony | Leafcutter |
|------------|------------|
| Colony | The Leafcutter runtime (Decision Kernel) |
| Worker | A capability: a LangGraph workflow with contracts, pre-checks and post-checks ([ADR-052](architecture/adrs/ADR-052-capabilities-replace-agents-prompts-are-compiled.md)) |
| Scout | Research and capability-gap handling: going where no capability exists yet |
| Food found | A task resolved and verified |
| Pheromone trail | A learned routing preference, built from verified outcomes |
| Dead-end trail | A failed path, or a decision later proven wrong |
| Evaporation | Evidence fading with age and with new policy, template or model versions |
| Colony memory | Execution statistics and decision outcomes ([ADR-056](architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md)) |
| Leaves → fungus garden | Raw LLM work, cultivated into ADRs, policies and workflows ([ADR-054](architecture/adrs/ADR-054-process-representation-and-maturity-model.md)) |
| Queen | The bootstrap. A human plus a general-purpose model found the colony, but they do not stay its central controller |

**Governing principle:** Leafcutter learns from the observed outcome of every capability invocation and important decision. Successful paths gain evidence, unsuccessful paths lose evidence, and repeated capability gaps create pressure for new specialized workflows.

**Safeguard:** usage alone is never evidence of correctness. A path called 5,000 times is popular, not proven. Only verified outcomes reinforce a trail, wrong decisions count against it, and some runs explore alternatives so an early bad choice cannot lock itself in. Trails may rank and propose; they may not legislate. Turning a trail into a policy or workflow stays a reviewed step.

Every question goes to the cheapest mechanism that can answer it reliably, in this order: deterministic code, then Jev, then an LLM, then a human ([ADR-053](architecture/adrs/ADR-053-intelligence-selection-deterministic-jev-llm-human.md)). Knowledge moves the same way over time, from LLM exploration to policy to workflow, and where possible to deterministic code (ADR-054).

Why it matters: software engineering rarely has empirical evidence about which of its processes and decisions work. A colony that records its outcomes produces exactly that evidence.

**Langfuse remembers what happened. The colony memory store remembers what Leafcutter learned.** Langfuse holds the complete history: every node traced, decisions scored, and confirmed mistakes kept as regression datasets ([ADR-058](architecture/adrs/ADR-058-langfuse-colony-history-scores-datasets.md)). Approved decisions are kept as reviewable records in Git and reused as precedent ([ADR-059](architecture/adrs/ADR-059-decision-store-reviewable-yaml-records-now-graph-later.md)). The learned statistics live as derived aggregates in an optional Neo4j store, updated after specific actions ([ADR-065](architecture/adrs/ADR-065-colony-learned-statistics-neo4j-aggregates.md), which supersedes ADR-057's PostgreSQL store). Without a configured store, Leafcutter works exactly the same, just without cross-run learning. A team can point everyone at one store and learn as one colony.

## Growing the Colony, Step by Step

The Decision Kernel is developed inside leafcutter-ai and is not yet shipped to adopters. It is built in stages, and each stage must leave the colony measurably stronger, not just bigger:

1. **Founding (kernel Stage 1 / V0).** The colony starts with no workers: the capability registry starts empty, and legacy agents and skills join only by recorded decision ([ADR-055](architecture/adrs/ADR-055-capability-registry-starts-empty.md)). The human and Claude still do most of the work. The kernel routes requests, makes bounded decisions with Jev, and records everything. Every trace carries the IDs and versions it needs to be counted later, because traces recorded without them can never be counted retroactively.
2. **First workers (Stages 2–3).** Retrieval, engineering workflows and executable component policies arrive as capabilities. This gives trails something to form on.
3. **Trails (Stage 4).** An evaluation job turns traces into a performance store. Wrong decisions and dead ends feed reviewed policy-gap and promotion proposals. Capability gaps are ranked by frequency, fallback cost and failure rate to propose what to build next; a human still sets the priority. Once the performance store exists and passes evaluation, routing starts to weigh historical success, failures and confidence calibration alongside semantic fit, and occasionally explores alternatives.
4. **Specialists (Stage 5).** Where scout evidence shows the colony still relies on the host for a kind of work, a specialized executor takes it over, and the general-purpose "queen/scout" intelligence becomes less central.

See [ADR-056](architecture/adrs/ADR-056-colony-memory-evidence-reinforcement.md) for the staged adoption plan.

## Current Phase

**Current phase:** Phase 1 — Stable portable MVP

**Highest-priority outcome:** A reliable package that installs into any project, self-onboards the user via interactive config, and produces correct agents/skills/hooks without manual fixup.

## What We're NOT Doing (Yet)

The following are explicitly out of scope until a future phase decision:

- Multi-LLM support for generative work (non-Anthropic models). Jev, a bounded decision model, is the deliberate exception (ADR-053)
- Package registry / versioned releases (npm, pip, etc.)
- GUI or web-based configuration interface
- A user-facing analytics dashboard product. Internal colony memory (traces, outcome records, performance statistics) *is* in scope (ADR-056)
- Plugin marketplace for community-contributed agents/skills

## Strategic Assets / Differentiators

| Asset | Description | Why it matters |
|-------|-------------|----------------|
| Config-driven templating | `{{config.*}}` injection compiles portable templates into project-specific agents | One template set serves all adopters; no fork-and-edit pattern |
| Build-system architecture | `build.py` with phase-based dispatch, compare-before-write, manifest tracking | Deterministic, auditable builds; drift detection via pre-commit hooks |
| AC-driven delivery | Each acceptance criterion carries its own agent assignments, sign-offs, and work status — the requirement IS the work order | Eliminates drift between specs and execution; supervisors walk the AC hierarchy directly without an intermediate ticket layer |
| Self-hosting dogfood | leafcutter develops itself using its own agents and skills (ADR-001) | Every UX issue is discovered during development, not after release |
| Quality gate suite | Pre-commit hooks for build drift, secrets, doc coverage, structural changes | Adopters get guardrails without writing their own hook infrastructure |
| Decision Kernel | Capabilities with contracts, checks and compiled prompts; Jev for bounded decisions; routing by process maturity (ADR-052–054) | The engineering process lives in software, not in giant prompts, and each decision uses the cheapest mechanism that can resolve it |
| Colony memory | Outcomes of capability runs and decisions are recorded (Langfuse history, approved decision records in Git, learned statistics in an optional Neo4j store) and fed back into routing and policy (ADR-056–059, ADR-065) | The system gets measurably better with use and produces evidence about which engineering processes work |

## Roadmap (Phases)

### Phase 1 — Stable Portable MVP

**Done when:** A fresh clone installs into a new project via `build.py --target-dir .`, the onboard wizard populates `skills_config.json`, and all generated agents/skills/hooks function correctly without manual intervention.

Establishes the core value proposition: one command to get a working AI dev workflow.

### Phase 2 — Ecosystem Hardening

**Done when:** The package handles version upgrades gracefully (template migrations, config schema evolution), supports multiple concurrent consumer projects from a single package clone, and has a documented contribution workflow for adding new agents/skills.

Unlocks adoption beyond the original author by making the package maintainable by others.

### Phase 3 — Distribution and Community

**Done when:** The package is installable via a standard package manager, has versioned releases with changelogs, and supports community-contributed agents/skills via a documented extension mechanism.

Transitions from a personal tool to a shared open-source package.

### Decision Kernel Track (parallel)

The colony stages from [Growing the Colony, Step by Step](#growing-the-colony-step-by-step) run as their own roadmap phases, `phase_kernel_1_founding` (active) through `phase_kernel_5_specialists`, in `docs/roadmap.json`. Every stage after founding has to show a colony-health improvement over the previous stage before it counts as done.

The colony memory store has its own track: `phase_colony_1_collect` → `phase_colony_2_analyze` → `phase_colony_3_suggest` → `phase_colony_4_influence` → `phase_colony_5_evolve` (ADR-057 §10). It only records until the statistics are calibrated. Historical evidence may influence routing only after held-out evaluation, so an early lucky path cannot lock itself in.

## Success Criteria

| Criterion | Target | How to measure |
|-----------|--------|----------------|
| Clean install success rate | 100% on supported platforms (Linux, macOS, WSL2) | Run `build.py --target-dir .` on a blank project with only `skills_config.json` present |
| Agent/skill compilation accuracy | Zero template injection errors | `build.py --validate-only` returns 0; no `{{config.*}}` placeholders survive in compiled output |
| Build idempotency | Consecutive builds produce zero git diff | Run `build.py` twice; `git status` shows no changes |
| Self-hosting parity | leafcutter's own workflow uses the same agents it ships | All leafcutter development tickets are driven by compiled agents from its own templates |

### Colony Health: How We Know It Is Getting Stronger

These are long-term measures for the Decision Kernel. They show a direction to track, not a target for the current phase.

| Measure | Healthy direction | Evidence source |
|---------|-------------------|-----------------|
| Share of requests resolved by specialized capabilities rather than fallback | Rising | Routing and outcome records |
| Decision accuracy and calibration per decision type | Rising, and closer to the stated confidence | Decision outcome records |
| Cost and time per resolved task | Falling | Langfuse traces |
| Rework rate after acceptance (repairs, reverts, overrides) | Falling | Outcome records |
| Recurrence of a capability gap after its capability ships | Near zero | Gap records |

## Key Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-09-30 | Langfuse is the colony history: every node traced, decisions scored, datasets as regression memory (ADR-058) | Detailed evidence of what happened, and a guard against relearning old mistakes |
| 2026-10-02 | Learned statistics live in Neo4j as derived aggregates updated after specific actions; Neo4j supersedes ADR-057's PostgreSQL store (ADR-065) | Statistics stay derived and rebuildable, never canonical; one learning store instead of PostgreSQL plus a graph |
| 2026-09-30 | Colony memory store is optional plain PostgreSQL behind a ColonyMemory port; a Supabase Postgres URL works, but the Supabase API is not used (ADR-057; store technology superseded by ADR-065) | Zero-install learning for adopters who add one URL; everything still works without it |
| 2026-09-30 | Colony memory: paths are reinforced by verified outcomes, never by usage alone (ADR-056) | Leafcutter learns which processes and decisions work, and capability gaps drive what gets built next |
| 2026-09-30 | The kernel's capability registry starts empty; legacy agents and skills join only by recorded decision (ADR-055) | The colony is founded on capabilities that meet the contract, not on inherited prompts |
| 2026-09-30 | Process representation and maturity levels 0–4 (ADR-054) | LLMs bootstrap process knowledge; repeated reasoning is promoted into policies and then workflows |
| 2026-09-30 | Intelligence selection: deterministic, then Jev, then LLM, then human (ADR-053) | Each question goes to the cheapest mechanism that can answer it reliably |
| 2026-09-30 | Capabilities replace agents; prompts are compiled from contracts (ADR-052) | The engineering process becomes software; prompts stop being its source of truth |
| 2026-05-19 | Self-hosting via config-driven paths, not `--self` flag (ADR-001) | More general; avoids special code paths. `skills_config.json` points paths into `leafcutter-ai/` for package development. |
| 2026-05-13 | YAML frontmatter stripping in template compilation | Keeps metadata in templates for tooling but out of compiled agent prompts |
| 2026-05-13 | Default overwrite semantics in build.py | Old skip-existing caused silently stale outputs; overwrite + compare-before-write is safer |
| 2026-05-14 | Compare-before-write guard | Eliminates mtime churn; `git status` stays clean for unchanged files |

## Epics Mapping

| Epic | Phase | Status | Notes |
|------|-------|--------|-------|
| EPIC-OnboardCompleteness | Phase 1 | active | Interactive onboard wizard and config validation |
| EPIC-LeafcutterVersioning | Phase 2 | planned | Version tracking, upgrade paths, migration support |
| EPIC-LeafcutterUpstreamChannels | Phase 3 | planned | Distribution, packaging, community extension points |

---

> See [CLAUDE.md](../CLAUDE.md) for the entry point that links here.
