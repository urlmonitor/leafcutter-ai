---
title: "Fix missing tail-tags in security-scanner skill DECISION HISTORY entries"
status: todo
components:
  - build_pipeline
created: 2026-05-26
depends_on: []
priority: high
phase: "Phase 1"
requires_diagram: false
requires_adr: false
roadmap_phase: phase_1
advances_current_outcome: true
files_touched:
  - leafcutter-ai/templates/skills/security-scanner/scripts/generate_security_report.py
  - leafcutter-ai/templates/skills/security-scanner/scripts/scan_dependencies.py
  - leafcutter-ai/templates/skills/security-scanner/scripts/scan_docker.py
  - leafcutter-ai/templates/skills/security-scanner/scripts/scan_secrets.py
agents:
  architect-review: not_needed
  python-coder: needed
  test-writer: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  change-scope-reviewer: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: not_needed
  status-checker: not_needed
  sql-coder: not_needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# 01: Fix missing tail-tags in security-scanner skill DECISION HISTORY entries

## Goal

In order to make the security-scanner skill scripts pass the `check_documentation`
pre-commit hook when installed into any downstream project, we need to append a
valid tail-tag (`(#TICKETLESS reason=...)`) to every DECISION HISTORY entry that
currently lacks one, so that the hook no longer raises a tail-tag violation.

## Context

The `check_documentation.py` hook enforces that every DECISION HISTORY entry ends
with either `(#EPIC-Name/NN)` or `(#TICKETLESS reason=<>=10-char reason>)`.

The four scripts in `leafcutter-ai/templates/skills/security-scanner/scripts/`
each contain an initial-implementation entry with no tail-tag:

```
# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.
```

This entry is present in:
- `generate_security_report.py` (inside the module docstring, line 13)
- `scan_dependencies.py` (inside the module docstring, line 13)
- `scan_docker.py` (inside the module docstring, line 14; line 18 already has a tag)
- `scan_secrets.py` (inside the module docstring, line 11)

Note that the DECISION HISTORY block in `generate_security_report.py` and
`scan_dependencies.py` and `scan_secrets.py` is embedded **inside the module
docstring** (between `"""` delimiters) — the hook still checks it. The entry
must be fixed in-place; the block placement is intentional and must not be moved.

The appropriate tail-tag is:
```
(#TICKETLESS reason=initial-skill-implementation)
```

This reason is 30 chars, satisfies the ≥10-char requirement, and clearly
communicates why there is no ticket reference.

## Acceptance Criteria

```gherkin
Given a downstream project built from the updated leafcutter templates
When the pre-commit hook check_documentation runs on any of the four security-scanner scripts
Then no "Missing tail-tag" violation is reported for those files

Given the updated generate_security_report.py
When inspected
Then line 13 ends with (#TICKETLESS reason=initial-skill-implementation)

Given the updated scan_dependencies.py
When inspected
Then line 13 ends with (#TICKETLESS reason=initial-skill-implementation)

Given the updated scan_docker.py
When inspected
Then line 14 ends with (#TICKETLESS reason=initial-skill-implementation)

Given the updated scan_secrets.py
When inspected
Then line 12 ends with (#TICKETLESS reason=initial-skill-implementation)
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] In `leafcutter-ai/templates/skills/security-scanner/scripts/generate_security_report.py`,
  append ` (#TICKETLESS reason=initial-skill-implementation)` to the line:
  `# - 2026-05-13 15:00 [epic-supervisor/ticket-23]: Initial implementation.`
- [ ] In `leafcutter-ai/templates/skills/security-scanner/scripts/scan_dependencies.py`,
  same fix on the same entry line
- [ ] In `leafcutter-ai/templates/skills/security-scanner/scripts/scan_docker.py`,
  same fix on line 14 (the initial-implementation entry; line 18 already has a tag)
- [ ] In `leafcutter-ai/templates/skills/security-scanner/scripts/scan_secrets.py`,
  same fix on the same entry line
- [ ] Add a DECISION HISTORY entry to each of the four files documenting this fix
  (with HH:MM and `(#EPIC-TemplateDocViolations/01)` tail-tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. These are template source files — no runtime data is affected.
- Reversibility? Fully reversible; the change is a string append to comments.
