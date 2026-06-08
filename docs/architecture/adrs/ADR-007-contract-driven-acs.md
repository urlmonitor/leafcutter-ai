---
title: "ADR-007: Contract-Driven Acceptance Criteria"
type: "adr"
status: "accepted"
created: "2026-06-04"
last_updated: "2026-06-04"
components:
  - build_pipeline
related_docs:
  - tickets/00_inbox/epics/EPIC-ContractDrivenACs/01_adr_contract_driven_acs.md
related_code: []
---

# ADR-007: Contract-Driven Acceptance Criteria

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-04 |
| Author | adr-author |
| Supersedes | — |

## Context

The leafcutter-ai agentic build pipeline produces features through a sequence of
phase agents — each agent receives acceptance criteria (ACs) for their phase and
signs off once the criteria are met. In the original design, ACs were written as
flat, business-level Gherkin scenarios in the ticket body, shared across all agents.

This created a recurring integration failure pattern: two agents would each sign
off on their own phase, both reading the same flat AC, yet produce artefacts that
could not be composed — for example, a python-coder implementing a function
signature that the pr-reviewer's AC described differently, or an sql-coder
writing a schema the python-coder later called with mismatched column names.

Root cause: **flat business ACs do not specify the interface boundary each agent
must honour when it delivers to its downstream consumer.** An agent has no
mechanically-verifiable contract telling it what it owes to the next agent in the
pipeline. The validation happens late (at PR review or integration test time),
by which point rework is expensive.

A second related issue emerged when epics grew beyond three or four tickets:
a single human Product Owner (PO) was bottlenecking ticket creation because
writing good ACs for technical agents requires deep system knowledge. The process
needed a two-phase creation pipeline — a business-level BA pass followed by a
technical IT PO pass — to distribute the cognitive load and ensure agents always
receive appropriately-scoped, technically-precise ACs.

## Decision

Acceptance criteria in the leafcutter-ai build pipeline MUST be restructured
from flat business-level Gherkin into **per-agent technical contracts**. Each
agent's AC block in the ticket body will carry an explicit "Delivers to" and
"Depends on" contract section describing the interface boundary the agent must
produce and the inputs it may assume.

The following design decisions hold as a bundle:

1. **Per-agent AC format.** Every agent listed in a ticket's `agents:` map MUST
   have a corresponding `### <agent-name>` block in the `## Agent Contracts`
   section. The block contains a numbered checklist of acceptance criteria, each
   written from the agent's perspective and testable without running the full
   system.

2. **Numbered checklist format instead of Gherkin.** Gherkin (Given/When/Then)
   is optimised for user-facing behavioural tests. Agent-to-agent contracts are
   structural and interface-level, not behavioural. Numbered checklists are
   easier to reference across ticket comments (e.g. "AC-3 is not met because…")
   and map directly to `completion_manifest:` items in the sign-off comment.

3. **Two-phase ticket creation pipeline.** Ticket creation MUST run in two
   sequential phases: (a) `business-analyst` writes the business-level intent,
   files_touched, and agent selection; (b) `product-owner-agent` (IT PO, running
   on Opus) reads the architecture docs — not the code — and writes per-agent
   technical contracts, "Delivers to" / "Depends on" blocks, and the
   `completion_manifest` checklist items. Single-agent creation (via `refinement`
   alone) is permitted only for low-complexity, single-agent tickets where no
   cross-agent interface exists.

4. **IT PO reads architecture docs, not code.** The IT PO agent reads
   `docs/architecture/`, `docs/how-to/`, ADRs, and existing agent templates to
   understand contracts — not source code. This ensures the PO's output reflects
   the intended design rather than incidental implementation details, and allows
   the PO to work from a stable abstraction boundary.

5. **Opus for the IT PO.** The semantic contract design step — inferring the
   interface each agent must produce, given the architecture — is the hardest
   cognitive task in ticket creation. It requires holding multiple agent
   perspectives simultaneously and reasoning about interface compatibility. The
   IT PO MUST run on Claude Opus. Lower-cost models are permitted for the
   `business-analyst` phase.

6. **`ac-validator` as a separate gate.** An `ac-validator` phase agent MUST be
   added to every ticket that contains a cross-agent interface (i.e. any ticket
   where more than one agent in `agents:` has status `needed`). The validator
   runs after all phase agents have signed off and before `commit`, and verifies
   that the `completion_manifest:` items from each agent's sign-off comment are
   consistent with the "Delivers to" contract declared in the AC block for the
   next agent in the chain. The validator does not re-run tests; it reads
   sign-off comments and verifies interface parity at the contract level.

## Consequences

### Benefits

- **Eliminated integration mismatches.** When each agent signs off on a
  per-agent contract, and the `ac-validator` checks interface parity across
  sign-off comments, integration failures are caught at ticket-close time rather
  than at code-review or system-test time.
- **Traceable sign-offs.** Each agent's `completion_manifest:` maps directly to
  its numbered AC checklist, making the audit trail from requirement to
  sign-off unambiguous.
- **Distributed cognitive load.** The BA → IT PO two-phase pipeline means no
  single human author needs to hold both business intent and technical interface
  details simultaneously. Each pass adds its own layer of precision without
  requiring the first author to anticipate all technical implications.
- **Architecture-doc-driven contracts.** IT PO reading architecture docs (not
  code) ensures contracts reflect the intended design abstraction, reducing the
  risk of contracts that encode accidental implementation details.

### Costs

- **Longer ticket creation.** Adding the IT PO pass increases ticket-creation
  time by one agent invocation (Opus, O(minutes) per ticket). For epics with
  many tickets, the aggregate creation time grows proportionally.
- **Opus cost.** Running the IT PO on Opus is significantly more expensive per
  token than Sonnet. For cost-sensitive deployments, the IT PO pass may be
  omitted for single-agent or trivially-simple tickets where no cross-agent
  interface exists. The `business-analyst` frontmatter flag
  `requires_it_po: false` explicitly documents when the IT PO pass is skipped.
- **`ac-validator` adds a mandatory phase.** Every multi-agent ticket now
  requires one additional phase agent in its pipeline. This increases overall
  ticket runtime and adds one more potential failure point for the supervisor
  adjudication ladder.

### Neutral

- The `signoff` skill's `completion_manifest:` block (EPIC-CompletionManifestSignoff)
  is the technical mechanism that makes per-agent ACs machine-readable at
  sign-off time. This ADR depends on that mechanism already being in place and
  does not modify it.

## Alternatives

### Alternative A — Sidecar JSON contract files

Write a separate `<ticket>.contracts.json` file alongside each ticket, encoding
each agent's "Delivers to" and "Depends on" fields in machine-readable JSON.

**Rejected.** Sidecar files fragment the ticket's information across two files,
making it harder to review in a single read. They require a separate schema and
parser. The numbered checklist format inside the ticket body is human-readable,
git-diffable, and requires no new file infrastructure.

### Alternative B — One AC per ticket (single shared AC set)

Keep a single set of ACs at the ticket level, but write them in a more precise
format (e.g. explicit input/output types per step) that all agents can interpret.

**Rejected.** A single AC set cannot simultaneously express agent-specific
constraints (e.g. "adr-author must produce a file at this path" vs "pr-reviewer
must verify the file has no broken cross-links"). Agents at different phases
have fundamentally different acceptance criteria that do not reduce to a single
shared specification without losing precision.

### Alternative C — Per-agent sign-off without a validator

Keep the current per-agent sign-off model (each agent signs off on its own phase)
but do not add the `ac-validator` gate.

**Rejected.** Without the validator, interface-level consistency checks across
the agent chain are manual and occur only when a human reviewer inspects the
full comment thread. The validator is the enforcement mechanism that makes
contract-driven ACs a structural guarantee rather than a naming convention.
Without it, two agents can each sign off on individually-correct work that is
collectively incompatible, with no automated detection.

## References

- EPIC-ContractDrivenACs `01_adr_contract_driven_acs.md` — the ticket that
  commissioned this ADR.
- `signoff` SKILL.md §2b — `completion_manifest:` schema that maps AC items to
  sign-off results.
- `agent_registry.json` — canonical agent list; the `ac-validator` entry will
  be added as part of EPIC-ContractDrivenACs implementation.
- ADR-006 — flatten-supervisor-chain; establishes the depth-0/depth-1 dispatch
  model that the IT PO and `ac-validator` agents operate within.
- EPIC-AgentProducesTrait — adds the `produces` trait to every agent in the
  registry. The `produces` value is a type-level declaration of an agent's
  primary output (e.g. `production_code`, `documentation`, `prompt`). When
  llm-expert cannot unambiguously infer the `produces` value (signals conflict),
  it sets `produces: null` and appends a structured `llm_ambiguity_comment` in
  the registry entry. The validation layer (`validate_produces_field()` in
  `scripts/registry_validator.py`) continues to emit an error for `null` entries
  until a human resolves the ambiguity, preventing silent data gaps in the
  registry. See AC BO-510-4-i and the `llm-expert` template §Produces Trait
  Inference and Ambiguity Flagging for the full protocol.
