---
title: "EPIC: AC Traceability Store — Centralized, Versionable Acceptance Criteria"
type: epic
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: medium
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: true
requires_adr: true
---

# EPIC: AC Traceability Store — Centralized, Versionable Acceptance Criteria

## Goal

In order to make Acceptance Criteria (ACs) first-class, addressable, and
versionable entities — rather than prose buried in ticket bodies — we need to
build a centralized `docs/acceptance-criteria/` store where each AC is a
standalone YAML file with an ID, component tag, Gherkin criteria, test
coverage links, and an amendment history, so that the BA, test-writer, and
triage agents can query ACs by component, track their evolution across tickets,
and classify test failures using live AC status.

## Context

The current state: ACs live in ticket bodies. They are duplicated when tickets
amend prior behaviour, they cannot be queried by component, they have no
lifecycle (active / deprecated / superseded), and test files have no machine-
readable link back to the AC they cover.

The consequences:
- The BA re-derives ACs from scratch on every ticket, risking silent
  contradiction of existing ACs.
- When a test fails, agents cannot determine whether the failure reflects a
  regression (AC still active, test is correct) or a staleness (AC was amended
  and the test is outdated).
- There is no single place to read "what behaviour does this component
  currently guarantee?"

This epic builds the AC store as a portable artifact installed by `build.py`
into any target project, with pre-commit enforcement to keep tests and ACs
bidirectionally linked.

### Key design decisions (settled — do not reopen)

- **AC files are the source of truth; tickets are the audit trail.** A ticket
  says "amend AC-FIN-001 to add the merge-first precondition." The AC file
  records the amendment in its `amended_by` list and the current Gherkin is
  updated. The ticket moves to done and is irrelevant to future queries.
- **IDs are component-scoped and stable.** `FIN-001`, `AUTH-001`, etc. Once
  assigned, an ID never changes. Superseded ACs are marked `status: superseded_by`
  with a pointer to the replacement.
- **Tests tag their AC.** A `# covers: FIN-001` comment in the test file is
  the machine-readable link. The pre-commit hook enforces bidirectional
  coverage.
- **`build.py` scaffolds the `docs/acceptance-criteria/` directory.** Like
  agents and hooks, the AC store skeleton is a portable template installed
  into any target project. The schema YAML validator is also installed as a
  pre-commit hook.

### Relationship to EPIC-FinalizeFeatureHardening

The `test-failure-triage` agent (FinalizeFeatureHardening ticket 03) works
standalone without this epic. When this epic ships, triage is enhanced: it
can look up the AC status for a failing test's `covers:` tag and classify
`stale_test` with much higher confidence (AC amended → test is stale;
AC active → test failure is a regression).

This epic is tracked separately as medium-term work. The triage enhancement
is captured in ticket 08 of this epic.

## Architecture Plan

### ADRs

- New ADR needed: "AC Store as portable template — schema, ID format, and
  directory layout for the acceptance-criteria store." This decision locks
  the YAML schema, ID format, and the bidirectional-enforcement model before
  implementation begins.

### Diagrams

- `data_flow` diagram at `docs/architecture/components/ac-traceability-store.md` (parent: `docs/architecture/components/`)

## Sub-ticket Table

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_ac_store_schema.md](./01_ac_store_schema.md) | Define AC YAML schema and write JSON Schema validator | `[ ]` |
| 02 | [02_ac_store_directory_scaffold.md](./02_ac_store_directory_scaffold.md) | Add docs/acceptance-criteria/ directory template to build.py scaffold | `[ ]` |
| 03 | [03_precommit_hook_test_tagging.md](./03_precommit_hook_test_tagging.md) | Pre-commit hook: every test function must have a `# covers: XX-NNN` tag | `[ ]` |
| 04 | [04_precommit_hook_ac_coverage.md](./04_precommit_hook_ac_coverage.md) | Pre-commit hook: every active AC must appear in at least one test's covers tag | `[ ]` |
| 05 | [05_ba_agent_ac_query.md](./05_ba_agent_ac_query.md) | Update BA agent to query existing ACs before writing new ones | `[ ]` |
| 06 | [06_test_writer_ac_integration.md](./06_test_writer_ac_integration.md) | Update test-writer to read AC files and emit covers: tags in tests | `[ ]` |
| 07 | [07_ticket_authoring_ac_workflow.md](./07_ticket_authoring_ac_workflow.md) | Update ticket-authoring skill: tickets reference ACs; BA creates/amends AC files | `[ ]` |
| 08 | [08_triage_agent_ac_lookup.md](./08_triage_agent_ac_lookup.md) | Enhance test-failure-triage to look up AC status for covers: tags (requires FinalizeFeatureHardening 03) | `[ ]` |
| 09 | [09_ac_store_docs.md](./09_ac_store_docs.md) | How-to and reference docs for the AC store | `[ ]` |
| 10 | [10_ac_origin_tracking.md](./10_ac_origin_tracking.md) | Extend AC schema with origin_agent field; stamp in BA agent, debug skill, and manual workflow | `[ ]` |
| 11 | [11_debug_skill_ac_lookup.md](./11_debug_skill_ac_lookup.md) | Add AC store query step to debug skill — inject active ACs into investigator prompts | `[ ]` |

## Execution Order

Ticket 01 (schema) must complete first. Tickets 02, 03, and 04 depend on 01.
Tickets 05, 06, 07 depend on 02 (store exists in a target project). Ticket 08
depends on 05, 06, and EPIC-FinalizeFeatureHardening ticket 03 (triage agent).
Ticket 09 depends on all prior tickets. Ticket 10 (AC origin tracking) depends
on 01 (schema must exist to amend it) and can run in parallel with 05–09.
Ticket 11 (debug skill AC lookup) depends on 02 and 05 (store scaffold and BA
query pattern must be established); it can run in parallel with 06–10.

## Risk & Safety

- Touches money? No.
- Touches data? No. The AC store is a new directory; no existing files are
  modified in the initial scaffold tickets.
- Reversibility? The store is an additive directory. Pre-commit hooks can be
  disabled individually. The BA/test-writer changes are amendments to
  template files; revertable via git.
- Migration risk: existing test files have no `covers:` tags. The pre-commit
  hooks (tickets 03 and 04) are introduced as warnings first, then errors
  in a follow-up grace-period ticket, to allow gradual adoption.
- The schema ADR (ticket 01 dependency) must be accepted before any YAML
  files are written to prevent schema churn.
