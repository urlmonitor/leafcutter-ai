---
title: 'Changelog 2026-06-04 — EPIC-ACTraceabilityStore: centralized AC store'
date: '2026-06-04'
time: 00:00
type: manual
components:
- build_pipeline
- precommit_hooks
- agent_registry
- documentation_system
summary: Added a centralized, versionable Acceptance Criteria store — a portable docs/acceptance-criteria/
  directory with YAML schema, bidirectional pre-commit enforcement, and AC-aware agent
  integrations across the BA, test-writer, ticket-authoring, triage, and debug agents.
description: '11 tickets, ~40 commits (PR #46). Built the AC store as a first-class
  artifact: ADR-008 defined the YAML schema and ID format; build.py gained a new scaffold
  phase to deploy docs/acceptance-criteria/ into any target project; two pre-commit
  hooks enforce bidirectional coverage (every test must carry a covers: tag, every
  active AC must appear in at least one test); the BA agent now queries existing ACs
  before authoring new ones; the test-writer emits covers: tags; the ticket-authoring
  skill gained a Step 2.5 AC-wiring convention; the test-failure-triage agent can
  look up AC status to classify stale-test vs regression; the debug skill injects
  active ACs into investigative prompts; and origin_agent was added to the AC schema
  so authoring provenance is machine-readable. How-to and reference docs were delivered
  as ticket 09.'
commits:
- ba1d3c0
- ba54532
breaking: false
created: '2026-08-13'
last_updated: '2026-08-13'
status: active
---
## Entry

### What shipped

**AC store scaffold (tickets 01, 02)**
- `docs/acceptance-criteria/` directory template added to `build.py` via a new `build_acceptance_criteria()` phase.
- `ac-schema.json` (JSON Schema v7) defines the canonical YAML format: id, component, status (active / deprecated / superseded_by), Gherkin criteria, test_coverage list, amended_by history, and origin_agent.
- ADR-008 documents all schema decisions and ID-format conventions (component-scoped stable IDs: `FIN-001`, `AUTH-001`, etc.).

**Pre-commit enforcement (tickets 03, 04)**
- `check_test_ac_tags.py`: every test function must carry a `# covers: XX-NNN` comment. Introduced as a warning gate with a grace period.
- `check_ac_coverage.py`: every active AC in the store must appear in at least one test's covers tag. Closes the bidirectional loop.

**Agent integrations (tickets 05–08, 11)**
- BA agent: queries `docs/acceptance-criteria/` before writing new ACs to prevent silent contradiction of existing ones.
- Test-writer: reads AC files and emits `# covers: XX-NNN` tags in generated tests.
- Ticket-authoring skill: new Step 2.5 wires ticket ACs to the store; BA creates or amends AC YAML files as part of ticket authoring.
- Test-failure-triage: looks up AC status for a failing test's covers tag — classifies `stale_test` (AC amended) vs regression (AC still active) with high confidence.
- Debug skill: injects active ACs into investigative prompts before spawning sub-agents.

**Schema extension (ticket 10)**
- `origin_agent` field added to AC YAML schema; BA agent, debug skill, and manual workflow all stamp it.

**Documentation (ticket 09)**
- How-to: `docs/how-to/ac-store-authoring.md` — authoring, amending, and superseding ACs.
- Reference: `docs/reference/ac-store-schema.md` — full schema field reference.

### Post-merge fix
- `fix(tests)`: `acceptance-criteria` added to `non_artifact_dirs` in the parity test (commit `ba54532`) after the merge surfaced a directory-layout assertion failure.
