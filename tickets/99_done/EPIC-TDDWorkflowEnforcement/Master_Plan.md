---
title: "EPIC: TDD Workflow Enforcement"
type: epic
status: done
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
---

# EPIC: TDD Workflow Enforcement

Flip the leafcutter build pipeline to true Test-Driven Development: the `test-writer` agent runs **before** coder agents and writes failing tests from the ticket's `## Test Requirements` block; coder agents (`python-coder`, `sql-coder`) receive a new success gate of making those failing tests pass without weakening the test suite; a three-layer contract-shrinking guard (pre-commit hook + supervisor check + honor-system docs) prevents test deletion/skip/xfail; and supervisor phase ordering, agent definitions, skills, and the ticket template are all updated to reflect the new canonical flow.

## Key Design Decisions

Scope decisions locked before authoring:
- **Retroactivity**: new tickets only. In-flight tickets (00_inbox/01_todo) continue under the old test-after flow.
- **Guard strictness**: all three layers — hook (blocks commit), supervisor (warns after coder phase), docs (explicit policy in agent definitions).
- **SQL TDD**: Python-only in this epic. SQL TDD is a follow-on (see ticket 08).
- **test-planner**: kept separate from test-writer (plans what to test in BA flow; writes failing tests in build flow).
- **Red-baseline**: mandatory. test-writer must capture the `red_baseline` structured block in its sign-off comment; coder success gate is "all red_baseline tests now green, no previously-passing test went red."
- **Refactor phase**: absorbed by existing `pr-reviewer` + code-simplifier review chain. No new agent added.
- **Docs-only / config-only skip rule**: if `## Test Requirements` has an empty `tests` array, skip test-writer entirely and proceed to the next phase agent.

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_agent_registry_priority_update.md](./01_agent_registry_priority_update.md) | Update agent_registry.json: move test-writer from priority 8 → 5 (before coders); update ticket-supervisor dispatch table | `[ ]` |
| 02 | [02_test_writer_rewrite.md](./02_test_writer_rewrite.md) | Rewrite test-writer agent: test-FIRST role, red-baseline capture contract, structured sign-off schema, docs-only skip rule | `[ ]` |
| 03 | [03_coder_success_gate.md](./03_coder_success_gate.md) | Update python-coder + sql-coder: add "make red-baseline green, no contract shrinking" success gate + honor-system docs | `[ ]` |
| 04 | [04_contract_shrinking_hook.md](./04_contract_shrinking_hook.md) | New pre-commit hook check_contract_shrinking.py: detects test deletion/skip/xfail when production code also changed | `[ ]` |
| 05 | [05_building_epics_skill_update.md](./05_building_epics_skill_update.md) | Update building-epics SKILL.md + ticket-supervisor.md: phase-order update + docs-only skip rule + supervisor-side contract-shrinking warn | `[ ]` |
| 06 | [06_ticket_authoring_template_update.md](./06_ticket_authoring_template_update.md) | Update ticket-authoring SKILL.md + ticket frontmatter template: Sign-offs order + agents map default ordering | `[ ]` |
| 07 | [07_tdd_documentation.md](./07_tdd_documentation.md) | Author explanation doc "How TDD works in leafcutter" + how-to "Writing a TDD ticket" + ADR-004 for workflow change | `[ ]` |
| 08 | [08_followup_sql_tdd_stub.md](./08_followup_sql_tdd_stub.md) | Follow-on stub: create SQL TDD epic in 00_inbox (placeholder so it is not forgotten) | `[ ]` |
