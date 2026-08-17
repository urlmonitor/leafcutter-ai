---
title: "ADR-017: Computed Quality Gates"
description: "Two-axis classification system (change_target x risk_surface) that maps ticket changes to mandatory guardrail agents at ticket-creation time."
type: adr
status: active
created: 2026-07-01
last_updated: 2026-07-01
components:
  - supervisor_system
  - ticket_creation_pipeline
  - agent_registry
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-007-contract-driven-acs.md
  - docs/architecture/components/build-ticket-workflow-dispatch.md
related_code:
  - scripts/ac_store/generate_ticket_from_ac.py
  - config/agent_registry.json
  - templates/agents/ticket-supervisor.md
  - templates/skills/building-epics/SKILL.md
---

# ADR-017: Computed Quality Gates

> Note on component IDs: `agent_registry` is used as the closest registered
> match for the produces-trait registry surface. The two-axis classification
> and the mapping computation are owned by `ticket_creation_pipeline`
> (generation-time materialisation) and `supervisor_system` (dispatch-time
> enforcement).

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-07-01 |
| **Author** | adr-author (EPIC-ComputedQualityGates) |
| **Supersedes** | None |

## Context

Quality gates — TDD (test-writer before / test-runner after a work agent),
code review, and documentation — have historically been implemented as
templates plus one-off guard rules. Each new coding agent or new risky
change type required a hand-edit to the supervisor's conditional logic, so
the gates were **inferred at dispatch time from hardcoded agent-name checks**
rather than **computed from the nature of the change**. This is brittle:
the guardrail decision was scattered across prompt prose, could drift out of
sync with the agent registry, and could not be audited from a ticket alone.

BO-510 (the agent `produces` trait, shipped by EPIC-AgentProducesTrait in
`tickets/99_done/`) removed the first source of brittleness. It lets each
agent declare what kind of artifact it generates from a fixed enum
(`production_code`, `documentation`, `configuration`, `prompt`,
`review_verdict`, `orchestration`, `test_artifact`, `analysis`). The trait
lives in two synchronised locations — `config/agent_registry.json` (source of
truth for dispatch) and each agent template's frontmatter (collocated for
readability) — with a validation test keeping them in lockstep. BO-510-5
wired `ticket-supervisor` to read that trait and select guardrails:
`production_code` triggers TDD; `documentation` skips it; `prompt` skips TDD
and applies prompt-quality guardrails instead.

The `produces` trait answers *"what does this agent make?"*. It does **not**
answer *"what does this change touch, and how much blast radius does it
carry?"*. Two tickets both assigned to `python-coder` (both `produces:
production_code`) can differ enormously in required rigour: a change to core
trading logic that mutates persisted data warrants far more gates than an
observability-only log-line tweak. Guardrail selection therefore needs a
second, change-shaped input in addition to the agent's produces trait.

This ADR records the decision to lift quality gates from inferred prose rules
into a **computed system invariant**: every change is classified along two
axes, each (change_target, risk_surface) pair maps to a mandatory set of
guardrail agents, and the full ordered agent map is **computed and
materialised into ticket frontmatter at ticket-generation time** — not
re-derived at dispatch time. As with every change in this repository, this
decision operates under the self-hosting boundary of
[ADR-001](ADR-001-self-hosting-boundary.md): leafcutter is modifying its own
templates, registry, and Python generation scripts. This work originates in
EPIC-ComputedQualityGates (ticket `01_adr_computed_quality_gates.md`) and
builds directly on the contract-driven AC model of
[ADR-008](ADR-007-contract-driven-acs.md).

## Decision

Quality gates **will** be a computed invariant of the ticket-generation
pipeline, defined by the following four commitments.

### 1. Two-axis change classification (AC-2AxisModel)

Every change **MUST** be classified along two orthogonal axes.

**Axis A — `change_target`** (what the change touches). It **MUST** take
exactly one of these ten values:

| # | `change_target` | Covers |
|---|---|---|
| 1 | `production_code` | Application/library source that ships behaviour |
| 2 | `test_artifact` | Test files, fixtures, test harness |
| 3 | `documentation` | Markdown docs, ADRs, how-tos, references |
| 4 | `prompt` | Agent templates, skill bodies, slash-command prompts |
| 5 | `configuration` | Config files, registries, build settings |
| 6 | `sql_schema` | DDL: tables, indexes, views, migrations |
| 7 | `sql_data` | DML: data inserts, backfills, data migrations |
| 8 | `frontend_code` | HTML/CSS/JS/TS/JSX/TSX/Vue/Svelte web-layer code |
| 9 | `infrastructure` | Hooks, CI, deployment, build pipeline |
| 10 | `data_pipeline` | ETL / ingestion / feature-computation flows |

**Axis B — `risk_surface`** (where the blast radius lands). It **MUST** take
exactly one of these six values:

| # | `risk_surface` | Blast radius |
|---|---|---|
| 1 | `core_logic` | Business-critical decision paths |
| 2 | `data_integrity` | Persisted state; correctness of stored data |
| 3 | `user_facing` | Surfaces a human directly observes |
| 4 | `integration` | Cross-service / cross-module contracts |
| 5 | `observability` | Logs, metrics, telemetry — no behaviour change |
| 6 | `none` | No meaningful blast radius (pure docs, comments) |

The two axes are orthogonal: `change_target` is intrinsic to the files
touched, `risk_surface` is a judgement about consequence. The pair
`(change_target, risk_surface)` **MUST NOT** be collapsed into a single axis.

### 2. Produces-trait gating of TDD guardrails (AC-ProducesTrait)

The computation **will** consume the assigned work agent's `produces` trait
(BO-510) as a precondition on the TDD guardrails. Specifically:

- An agent whose registry `produces` value is `production_code` **MUST** have
  the TDD guardrails applied: `test-writer` runs before the work agent and
  `test-runner` runs after it.
- An agent whose `produces` value is `documentation` **MUST NOT** have TDD
  guardrails injected.
- An agent whose `produces` value is `prompt` **MUST NOT** have TDD guardrails
  by default; prompt-quality guardrails apply instead where defined.

This preserves the BO-510-5 dispatch contract already shipped in
`ticket-supervisor` and `building-epics` SKILL.md: the produces trait gates
*whether TDD applies to the work agent at all*, and the two-axis classification
then determines *which additional mandatory gates* stack on top.

### 3. (change_target, risk_surface) → mandatory-gate mapping (AC-MapTable)

Each `(change_target, risk_surface)` pair **will** map to a mandatory set of
guardrail agents. The mapping is the single authoritative definition of
required gates. The illustrative core of the mapping is:

| change_target | risk_surface | Mandatory guardrail agents (in addition to always-on `commit`, `pull-request`) |
|---|---|---|
| `production_code` | `core_logic` | `test-writer`, `test-runner`, `pr-reviewer`, `ac-validator` |
| `production_code` | `data_integrity` | `test-writer`, `test-runner`, `pr-reviewer`, `ac-validator` |
| `production_code` | `observability` | `test-runner`, `pr-reviewer` |
| `sql_schema` | `data_integrity` | `test-writer`, `test-runner`, `pr-reviewer`, `ac-validator` |
| `sql_data` | `data_integrity` | `test-writer`, `test-runner`, `pr-reviewer`, `ac-validator` |
| `frontend_code` | `user_facing` | `test-writer`, `test-runner`, `pr-reviewer`, `user-surface-smoker` |
| `prompt` | `integration` | `pr-reviewer` (prompt-quality), `ac-validator` |
| `documentation` | `none` | `pr-reviewer` |
| `infrastructure` | `integration` | `test-writer`, `test-runner`, `pr-reviewer` |
| `data_pipeline` | `data_integrity` | `test-writer`, `test-runner`, `pr-reviewer`, `ac-validator` |

The general rule the table encodes: TDD gates (`test-writer`/`test-runner`)
are mandatory whenever the work agent `produces: production_code` **and** the
`risk_surface` is anything other than `observability` or `none`; `ac-validator`
is mandatory whenever `risk_surface` is `core_logic`, `data_integrity`, or a
cross-boundary `integration`; `user-surface-smoker` is mandatory whenever
`risk_surface` is `user_facing`; `pr-reviewer` is mandatory for every pair.
The table above is the canonical starting set — new pairs are added by editing
the mapping data, never by editing supervisor prose.

### 4. Generation-time materialisation in Python (AC-Computation)

The computed agent map **MUST** be materialised into the ticket's frontmatter
`agents:` block at ticket-generation time by the Python function
`_build_agents_map` in `scripts/ac_store/generate_ticket_from_ac.py`. It
**MUST NOT** be re-derived by the supervisor at dispatch time.

`_build_agents_map(assigned_agent)` today computes the ordered `agents:` map
from three named agent groups declared as module constants:
`_CANONICAL_SUPPORT_AGENTS` (`test-writer`, `test-runner`, `pr-reviewer`,
`commit`, `pull-request` — all set `needed`), `_SQL_AGENTS` (`sql-coder`,
set `not_needed` unless the assigned agent is `sql-coder`), and
`_NOT_NEEDED_AGENTS` (`documentation-expert`, set `not_needed`). This decision
extends that function so its inputs become the pair
`(change_target, risk_surface)` plus the assigned agent's `produces` trait,
and its output is the mapping-table result (§3) gated by the produces trait
(§2). The function **will** emit the same ordered `dict[str, str]` shape it
emits today, so the downstream `_build_signoffs_section` and `_build_frontmatter`
helpers — and the parity guard `check_ticket_signoff_parity.py` — continue to
consume it unchanged. The result is that a generated ticket carries its full,
already-decided quality-gate set as data in frontmatter; the supervisor's job
is reduced to executing that data in order.

### 5. Self-hosting boundary (AC-SelfHosting)

This decision **will** be implemented within the self-hosting boundary defined
by [ADR-001](ADR-001-self-hosting-boundary.md). Every artifact changed by
EPIC-ComputedQualityGates is leafcutter modifying *itself*: the agent
templates under `templates/agents/`, the `config/agent_registry.json`
registry that carries the `produces` trait, and the Python generation script
`scripts/ac_store/generate_ticket_from_ac.py`. Per ADR-001, all of these live
under `leafcutter-ai/` as package source and are re-deployed by `build.py`;
none are hand-edited build outputs. The mapping data and the classification
enums **MUST** therefore live in the package source tree so that a consumer
project that installs leafcutter inherits the identical computed-gate
behaviour after running `build.py`. leafcutter dogfoods its own gates: the
tickets that build this feature are themselves generated with the computed
agent map.

## Consequences

**Positive:**

- Guardrail selection becomes **auditable from the ticket alone** — the
  `agents:` frontmatter is the record of exactly which gates were required.
- Adding a new change/risk pair or a new gate is a **data edit** to the
  mapping and the module constants, not a prose edit to supervisor logic that
  can silently drift.
- The produces trait (BO-510) and the two-axis model compose cleanly: the
  trait gates *whether* TDD applies; the axes determine *what else* stacks on.
- Consumer projects inherit identical gate behaviour through `build.py`,
  because the mapping lives in package source (ADR-001).
- The computed map reuses the existing `agents:` shape, so the parity guard,
  Sign-offs section, and supervisor dispatch continue to work unchanged.

**Negative:**

- Two more required inputs (`change_target`, `risk_surface`) must be present
  and correct for every AC/ticket; a mis-classification silently under- or
  over-gates. This shifts rigour onto the classification step.
- The mapping table is a maintained artifact — it must be kept exhaustive as
  new `change_target` or `risk_surface` values are introduced.
- Materialising at generation time means a stale ticket generated before a
  mapping change carries the old gate set; regenerating or a re-classification
  pass is required to pick up mapping updates.

**Operational:**

- `_build_agents_map` gains `(change_target, risk_surface)` and the assigned
  agent's `produces` value as inputs; its unit tests must cover the mapping
  matrix and the produces-trait gating branches.
- Ticket generation must fail loudly (not default silently) when
  `change_target` or `risk_surface` is missing or outside the enum, so
  mis-classification is caught at generation time rather than surfacing as a
  missing gate at dispatch time.
- The mapping data and both enums are validated in sync with the registry, in
  the same spirit as the BO-510 registry/template parity test.

## Alternatives

- **Single-axis classification (change_target only).** Rejected: a single
  axis cannot distinguish an observability-only log tweak from a core-logic
  mutation within the same `production_code` target, so it would either
  over-gate cheap changes or under-gate risky ones. The `risk_surface` axis
  is what carries blast-radius judgement.

- **Infer gates at dispatch time from agent name (status quo before BO-510).**
  Rejected: dispatch-time inference from hardcoded agent names is exactly the
  brittleness EPIC-AgentProducesTrait set out to remove — it scatters the
  guardrail decision across supervisor prose, drifts from the registry, and is
  not auditable from a ticket.

- **Compute gates at dispatch time from the two axes (not at generation).**
  Rejected: computing at dispatch time leaves the ticket frontmatter an
  incomplete record and forces every supervisor invocation to re-run the
  mapping. Materialising once at generation time makes the ticket the durable,
  auditable source of truth and keeps the supervisor a pure executor.

- **Store gate rules only in supervisor prompt prose (no Python mapping).**
  Rejected: prose rules cannot be unit-tested, are invisible to the parity
  guard, and re-introduce the drift problem. A Python mapping consumed by
  `_build_agents_map` is testable and lives in package source per ADR-001.
