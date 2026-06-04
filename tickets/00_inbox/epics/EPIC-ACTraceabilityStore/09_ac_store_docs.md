---
title: "How-to and reference docs for the AC Traceability Store"
status: todo
components:
  - build_pipeline
created: 2026-06-04
depends_on:
  - 01_ac_store_schema.md
  - 02_ac_store_directory_scaffold.md
  - 03_precommit_hook_test_tagging.md
  - 04_precommit_hook_ac_coverage.md
  - 05_ba_agent_ac_query.md
  - 06_test_writer_ac_integration.md
  - 07_ticket_authoring_ac_workflow.md
  - 08_triage_agent_ac_lookup.md
priority: low
roadmap_phase: phase_2
advances_current_outcome: false
requires_diagram: false
requires_adr: false
files_touched:
  - templates/docs/how-to/ac-traceability-store.md
  - templates/docs/reference/ac-schema.md
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: not_needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: needed
  reference-author: needed
  user-surface-smoker: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
requires_documentation:
  - how_to
  - reference
---

# 09: How-to and reference docs for the AC Traceability Store

## Actor / Goal

In order to enable new users and downstream agents to understand and use the
AC store correctly, we need to write a how-to guide and a reference doc that
cover the store's purpose, structure, lifecycle operations, and integration
points, so that adoption does not require reading multiple agent templates or
skill files.

## Context

The AC store spans pre-commit hooks, agent templates, and ticket-authoring
conventions. Without a consolidated how-to, users must piece together the
model by reading seven different files. This ticket produces two portable
template docs installed by build.py into any target project.

### how-to/ac-traceability-store.md

A task-oriented guide covering:
1. "How do I create a new AC?" — write the YAML, run the validator, reference
   it from a ticket.
2. "How do I amend an existing AC?" — update the criteria, add the ticket to
   amended_by.
3. "How do I deprecate an AC?" — set status: deprecated, no other changes needed.
4. "How do I add covers: tags to existing tests?" — the backfill procedure.
5. "What happens when a test fails triage because its AC is deprecated?" —
   remove the test or re-tag it to the superseding AC.

### reference/ac-schema.md

A reference doc covering:
- Every field in the AC YAML schema with type, required/optional, and semantics.
- The ID format and assignment process.
- The status lifecycle diagram (active → deprecated / superseded_by).
- The pre-commit hooks and their enforcement modes.
- The agent integration points (BA, test-writer, triage).

## Acceptance Criteria

```gherkin
Given docs/how-to/ac-traceability-store.md is installed in a target project
When a user reads "How do I create a new AC?"
Then they can follow the steps without reading any agent template or skill file

Given docs/reference/ac-schema.md is installed
When a downstream agent reads the reference doc
Then it can construct a valid AC YAML file from the reference alone
 And it can determine the pre-commit hook enforcement mode from the reference

Given build.py runs on a fresh project
When the scaffold phase completes
Then both docs are present in the target project's docs/how-to/ and docs/reference/
```

## Sign-offs

- [ ] documentation-expert
- [ ] how-to-author
- [ ] reference-author
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] Create `templates/docs/how-to/ac-traceability-store.md` following
  the how-to doc template (task-oriented, step-by-step, no conceptual
  tangents). Cover the 5 tasks listed in Context above.
- [ ] Create `templates/docs/reference/ac-schema.md` following the
  reference doc template (complete, precise, no tutorials). Cover all fields,
  ID format, status lifecycle, hooks, and agent integrations.
- [ ] Wire both files into the `build.py` doc scaffold phase so they are
  installed to `docs/how-to/` and `docs/reference/` in the target project.
- [ ] Validate that build.py --validate-only exits 0 after the wiring.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? New files. Fully reversible.
- This ticket is the final ticket in the epic. It should only be executed
  after all prior tickets are complete, to ensure the docs accurately reflect
  the implemented system.
