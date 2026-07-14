---
title: "Reference-pattern resolution in ticket generator + un-phantom the coverage labels"
status: todo
components:
  - build_orchestration
created: 2026-07-14
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
source_ac: BO-2000c-3
ac_coverage:
  - BO-2000c-3
  - BO-2000c-3-i
files_touched:
  - scripts/ac_store/generate_ticket_from_ac.py
  - unit_tests/prompt_assembly/test_implementation_notes_emission.py
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

# 05: Reference-pattern resolution + un-phantom coverage

## Actor / Goal

As the ticket generator, I want `it_requirements` reference patterns (globs)
resolved to concrete paths with an explicit error on unresolvable patterns, so
BO-2000c-3 is real — and the coverage labels must sit on a test that actually
exercises it.

## Remediation Context (audit 2026-07-14)

**Missing behaviour + phantom coverage.** `generate_ticket_from_ac.py` serialises
`it_requirements` verbatim to YAML; there is **no glob→concrete-path resolution
and no unresolvable-pattern error path** (BO-2000c-3 / c-3-i). The `# covers:
BO-2000c-3 / -3-i` labels were placed on
`test_dispatch_prompt_instructs_read_ticket_and_stays_thin` (a build-ticket.js
dispatch-string test) that does not exercise path resolution at all.

**Do:** implement reference-pattern resolution + the authoring-error path; move
the `covers` labels onto a test that genuinely asserts resolution.

## Acceptance Criteria

Resolves BO-2000c-3, BO-2000c-3-i (verbatim Gherkin under
`.../BO-2000-correct-prompts-by-construction/`).

## Test Requirements

```yaml
tests:
  - name: test_reference_pattern_resolves_to_paths
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    covers: [BO-2000c-3]
    asserts: a glob reference pattern in it_requirements is resolved to concrete file paths.
  - name: test_unresolvable_pattern_errors
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    covers: [BO-2000c-3-i]
    asserts: an unresolvable reference pattern raises an authoring error (no silent pass).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
