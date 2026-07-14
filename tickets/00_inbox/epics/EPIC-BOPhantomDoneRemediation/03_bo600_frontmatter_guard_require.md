---
title: "Frontmatter guard: require change_target/risk_surface and reject null/empty"
status: todo
components:
  - guardrail_engine
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BO-610-4
ac_coverage:
  - BO-610-3-i
  - BO-610-4
  - BO-610-4-i
  - BO-630-1-i
files_touched:
  - templates/hooks/ticket_frontmatter_guard.py
  - unit_tests/test_ticket_frontmatter_guard.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 03: Frontmatter guard requires fields + rejects null/empty

## Actor / Goal

As the guardrail engine, I want `ticket_frontmatter_guard` to *require*
`change_target`/`risk_surface` and reject null/empty values, so the BO-610 ACs
are actually enforced rather than contradicted.

## Remediation Context (audit 2026-07-14)

**Opposite behaviour + phantom tests.** The guard currently makes both fields
*optional* and accepts null/empty; its tests (`test_null_change_target_passes`,
`test_absent_risk_surface_passes`) assert **exactly the behaviour the ACs say to
reject**. `BO-630-1-i` model-tier default/validation is dead (helpers never
called, no `XL`-invalid error, no default `M`).

**Do: make the fields required, reject null/empty with a "Missing required
field"/"invalid value" error, and rewrite the inverted tests to assert the AC
behaviour (not its opposite).** Confirm no legitimate caller relied on the fields
being optional before flipping (call-site audit).

## Acceptance Criteria

Resolves BO-610-3-i, BO-610-4, BO-610-4-i, BO-630-1-i (verbatim Gherkin under
`.../guardrail-engine/BO-600-change-driven-guardrails/`).

## Test Requirements

```yaml
tests:
  - name: test_absent_change_target_is_rejected
    file: unit_tests/test_ticket_frontmatter_guard.py
    covers: [BO-610-4, BO-610-4-i]
    asserts: a ticket missing change_target/risk_surface fails with a required-field error.
  - name: test_null_or_empty_axis_is_rejected
    file: unit_tests/test_ticket_frontmatter_guard.py
    covers: [BO-610-3-i]
    asserts: null or empty change_target/risk_surface is rejected (replaces the inverted test).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
