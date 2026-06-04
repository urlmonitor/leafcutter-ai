---
title: "EPIC: Unify v2 Ticket Pipeline with AC Traceability Store"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: Unify v2 Ticket Pipeline with AC Traceability Store

## Goal

Connect the v2 ticket-creation pipeline (BA-v2 + IT PO + ac-validator) to the
centralized AC Traceability Store (`docs/acceptance-criteria/`), so that:
- AC YAML files are created/amended when tickets are created via `/create-ticket-v2`
- A deterministic pre-commit hook enforces that ticket AC references resolve to
  active store entries (Option B — blocking)
- The full traceability triangle is complete: tickets → ACs, ACs → tests, tests → ACs

## Context

Two separate epics built these systems independently:

- **EPIC-ContractDrivenACs** built `/create-ticket-v2` with inline numbered ACs,
  per-agent contracts, and `ac_coverage` frontmatter. But the v2 pipeline does NOT
  write AC YAML files to the store.

- **EPIC-ACTraceabilityStore** built `docs/acceptance-criteria/` with schema,
  `index.yaml`, and wired it into the v1 BA, test-writer, and triage agent. But
  the v2 pipeline was never connected.

Result: the AC store scaffold exists (`index.yaml` + one `finalize` component)
but contains zero actual AC YAML files because neither pipeline has run against
real tickets since the wiring was completed.

### Design decisions (settled)

1. **AC store cross-check is a deterministic script, not an LLM.** The check
   "does AC-FIN-001 exist as an active YAML file?" is structural/mechanical.
   Pattern: same as `check_ac_coverage.py` and `check_test_ac_tags.py`.

2. **Option B — blocking enforcement.** Missing store correspondence = blocker.
   Graceful degradation when `docs/acceptance-criteria/` doesn't exist (exit 0).

3. **BA-v2 owns AC classification** (before routing to IT PO), matching the v1
   design where BA runs before any routing decisions.

## Sub-Tickets

| # | File | Description | Depends on | Status |
|---|------|-------------|------------|--------|
| 01 | [01_v2_pipeline_ac_store_alignment.md](./01_v2_pipeline_ac_store_alignment.md) | Wire AC store query + YAML writes into BA-v2 and create-ticket-v2 | — | todo |
| 02 | [02_ac_store_inline_alignment_hook.md](./02_ac_store_inline_alignment_hook.md) | Deterministic pre-commit hook: verify ticket AC refs resolve to active store entries | 01 | todo |

## Execution Order

Ticket 01 must complete first — it produces the AC YAML files that ticket 02's
hook validates. Sequential execution only.

## Risk & Safety

- Touches money? No.
- Touches data? Writes new `.yaml` files to `docs/acceptance-criteria/` (same as v1).
- Reversibility? Fully reversible — template edits + new script file + config entry.
- v1 pipeline is untouched. Only v2 templates are modified.
