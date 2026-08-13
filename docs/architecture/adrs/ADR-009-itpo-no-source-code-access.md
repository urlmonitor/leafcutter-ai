---
title: 'ADR-009: IT Product Owner v3 — Source Code Access Restriction'
type: adr
status: accepted
created: '2026-06-05'
last_updated: '2026-06-05'
deciders:
- BrainCandy
requires_ac: TKT-300a
components:
- build_pipeline
related_docs:
- docs/architecture/adrs/ADR-007-contract-driven-acs.md
- config/agent_registry.json
- docs/components.json
description: 'Overview of ADR-009: IT Product Owner v3 — Source Code Access Restriction.'
---
# ADR-009: IT Product Owner v3 — Source Code Access Restriction

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-05 |
| Deciders | BrainCandy |
| Requires AC | TKT-300a |
| Author | adr-author |
| Supersedes | — |

## Context

The leafcutter-ai build pipeline produces features through a two-phase ticket
creation pipeline: a `business-analyst` (BA) pass writes business-level intent
and agent selection; an `product-owner-agent` (IT PO) pass enriches L2/L3
acceptance criteria with technical fields — `assigned_agent`, `it_requirements`,
and `delivers_to`/`expects_from` interface contracts. This two-phase design is
mandated by ADR-008.

The initial IT PO v3 template was drafted with permission to read source code
files (`.py`, `.ts`, `.sql`) to understand the implementation landscape when
making assignment and splitting decisions. The rationale at the time was that
an IT PO with richer context would produce more accurate `it_requirements`
blocks.

After review, this was identified as **scope creep** that harms the system's
long-term stability for several reasons:

1. **Role blur.** A real IT Product Owner operates at the architecture and
   component level, not the implementation level. Reading source code draws the
   IT PO into the coder role — knowing which exception types a module raises,
   which exit codes a CLI tool uses, or how a specific query is structured.
   That knowledge is the coder's domain.

2. **Over-prescriptive `it_requirements`.** When the IT PO reads source code, its
   generated `it_requirements` entries tend to name specific implementation
   artefacts: exception class names, column names, internal function signatures.
   These prescriptions are not constraints — they are leakage from the
   implementation into the contract layer, making the contract brittle.

3. **Refactor sensitivity.** Contracts written with reference to specific source
   code break silently whenever that code is refactored. The IT PO cannot
   know whether a contract it wrote six weeks ago still reflects the current
   code, because it has no standing read access between ticket runs.

4. **Redundancy when docs are rich.** `config/agent_registry.json` (60+ agents
   with roles and capabilities), `docs/components.json` (component boundaries,
   `primary_code` paths, agent affinity), `docs/architecture/` (C4 diagrams, data
   flows, ADRs), and `docs/acceptance-criteria/` (existing contracts) provide
   everything an IT PO needs to make correct assignment, splitting, and interface
   decisions. Source reading is redundant when these documents are maintained.

ADR-008 decision item 4 states explicitly: "IT PO reads architecture docs, not
code." This ADR formalises that decision as a named constraint with the IT PO v3
template as its scope, documents the permitted knowledge sources, and records
the trade-off against the completeness requirement it creates for
`docs/components.json`.

## Decision

**The IT PO v3 agent MUST NOT read source code files.** This restriction applies
to any file whose primary purpose is implementation: `.py`, `.ts`, `.js`, `.sql`,
`.sh`, configuration files that encode runtime behaviour (e.g. `pyproject.toml`,
`package.json`), and test files.

The IT PO v3 agent's permitted knowledge sources are, in priority order:

| Source | Path | What the IT PO uses it for |
|---|---|---|
| Agent registry | `config/agent_registry.json` | Canonical list of 60+ agents with roles, capabilities, and model tier. Used for `assigned_agent` decisions. |
| Component registry | `docs/components.json` | Component boundaries, `primary_code` paths, `agent_affinity`, `exposed_interfaces`, `depends_on`. Used for splitting and contract decisions. |
| Architecture docs | `docs/architecture/` | C4 diagrams, data flow docs, ADRs. Used for understanding system shape and prior decisions. |
| Existing ACs | `docs/acceptance-criteria/` | Standing contracts and `delivers_to`/`expects_from` pairs. Used for consistency and reuse. |
| Project policies | `PROJECT_CONTEXT.md`, `CLAUDE.md` | Constraints, conventions, and tooling. Used for `it_requirements` policy fields. |

The IT PO MUST flag a gap and halt enrichment (rather than fall back to reading
source code) when the above sources do not provide sufficient information to
write a defensible contract. The flag MUST appear as a `## Blockers` item in
the ticket body identifying which component's docs are stale or missing.

This constraint implies a **completeness obligation on `docs/components.json`**.
For the IT PO to make good decisions without source access, `components.json`
MUST carry at minimum:

- `agent_affinity` — which agent(s) own this component
- `exposed_interfaces` — what the component offers to its callers
- `component-level depends_on` — which other components this component consumes

These fields are tracked for enrichment by ACS-300g through ACS-300j (component
registry enrichment tickets). Until those tickets are complete, the IT PO may
produce lower-quality contracts in areas where `components.json` is sparse; this
is an accepted cost of the transition period.

## Consequences

### Positive

- **Clean role separation.** PO reads customer docs; BA reads domain docs; IT PO
  reads architecture docs; coders read source. The knowledge plane for each
  agent tier is non-overlapping and independently maintainable.
- **Policy-level `it_requirements`.** Without source access, IT PO constraints
  stay at the policy level (timeouts, retry counts, log format, error category)
  rather than encoding implementation specifics (exception class names, SQL
  column names). Policy-level requirements survive refactors.
- **Stable contracts under refactor.** A contract written at the architecture
  level remains valid after an internal refactor that does not change the
  component's interface. The IT PO does not need to be re-run when source is
  refactored, only when architecture or component boundaries change.
- **Documentation-quality pressure.** Requiring IT PO to work from `components.json`
  creates a forcing function for keeping architecture docs current. Staleness is
  visible (the IT PO flags it) rather than hidden (the IT PO guesses from stale
  source and produces a subtly-wrong contract).

### Negative

- **Requires investment in `components.json`.** For the restriction to work
  without degrading contract quality, `components.json` must carry `agent_affinity`,
  `exposed_interfaces`, and `depends_on` fields. This is non-trivial enrichment
  work tracked by ACS-300g–ACS-300j.
- **Lower-quality contracts during transition.** Before ACS-300g–ACS-300j are
  complete, the IT PO will encounter components with insufficient `components.json`
  coverage. Contracts for those components will be coarser-grained. Teams must
  review IT PO output more carefully during this window.
- **No fallback when architecture docs are stale.** If `components.json` and
  `docs/architecture/` are both stale for a given component, the IT PO has no
  fallback mechanism. It must halt and flag the gap. A halted IT PO is better
  than an IT PO that produces a silently-wrong contract, but it does introduce a
  potential pipeline blocker during enrichment sprints.

### Neutral

- The `business-analyst` agent is unaffected by this decision. The BA reads
  business requirements and domain documentation; it does not read architecture
  docs or source code.
- Coder agents (`python-coder`, `sql-coder`, `frontend-coder`) continue to read
  source code as their primary knowledge source. This decision does not change
  their access model.
- The `ac-validator` agent (introduced by ADR-008) reads sign-off comments and
  `completion_manifest:` blocks, not source code. It is unaffected.

## Alternatives

### Alternative A — Allow source reading (status quo v3 draft)

Keep the IT PO v3 template as-drafted with permission to read `.py`, `.ts`, and
`.sql` files.

**Rejected.** This alternative blurs the IT PO role with the coder role, leads
to over-prescriptive `it_requirements`, and creates contracts that are fragile
under refactoring. The short-term gain in contract completeness does not
outweigh the long-term cost of role blur and refactor sensitivity. See Context
section for the detailed failure modes.

### Alternative B — Allow source reading for specific file types only

Permit the IT PO to read only interface definition files (e.g. Python `__init__.py`
re-exports, TypeScript `.d.ts` files) but not implementation files.

**Rejected.** The restriction is difficult to enforce: the boundary between
"interface definition" and "implementation" is not consistently enforced across
the codebase. In practice, agents allowed to read some source files drift toward
reading more. The role-blur problem is not eliminated, only narrowed. The
correct fix is to surface interface information in `components.json` rather than
requiring the IT PO to extract it from source.

### Alternative C — "Code summary" skill

Give the IT PO a `code-summary` skill that accepts a component name and returns
architecture-level information derived from source (e.g. public function
signatures, exported constants), without exposing raw source to the agent.

**Not rejected — deferred.** This approach has merit if `components.json`
turns out to be too expensive to maintain at the required fidelity. A
`code-summary` skill could be implemented as a wrapper over static analysis
tools (e.g. `ast` module for Python, `ts-morph` for TypeScript) that extracts
only public API surface. It is tracked as a future enhancement. For the current
phase, it is not needed if the ACS-300g–ACS-300j enrichment delivers the
required `components.json` coverage.

## References

- ADR-008 — Contract-Driven Acceptance Criteria; decision item 4 establishes
  the principle that IT PO reads architecture docs, not code.
- TKT-300a — IT PO enrichment spec; the ticket that scopes IT PO v3 behaviour.
- TKT-100l — BA writes behavior, IT PO adds implementation; establishes the
  two-phase authorship model.
- ACS-300f — Unified component registry; the base schema for `components.json`.
- ACS-300g through ACS-300j — Component registry enrichment: `agent_affinity`,
  `exposed_interfaces`, and `depends_on` fields that are the enabling condition
  for this ADR to deliver full contract quality.
- `config/agent_registry.json` — canonical agent list used by IT PO for
  `assigned_agent` decisions.
- `docs/components.json` — component registry; must be kept current for this
  ADR's trade-off to hold.
