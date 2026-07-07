---
title: "Component-registry governance validation + AC-hook UTF-8 fail-open"
status: todo
components:
  - ac-store
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/8
source_acs:
  - ACS-300g-1
  - ACS-300g-2
  - ACS-300h-1
  - ACS-300i-1
  - ACS-300i-2
  - ACS-300j-1
  - ACS-300k-1
  - ACS-100i-2-i
ac_path: docs/acceptance-criteria/ac-store/
files_touched:
  - scripts/commit_guardian/check_components_integrity.py
  - templates/scripts/commit_guardian/check_components_integrity.py
  - scripts/build_phases.py
  - scripts/commit_guardian/check_ac_parent_covered_by.py
  - templates/scripts/commit_guardian/check_ac_parent_covered_by.py
  - unit_tests/commit_guardian/test_check_components_integrity.py
  - unit_tests/commit_guardian/test_check_ac_parent_covered_by.py
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
  adr-author: not_needed
  architecture-diagram-author: not_needed
complexity: standard

---

# Component-registry governance validation + AC-hook UTF-8 fail-open

## Actor / Goal

As the leafcutter package, we need `check_components_integrity.py` to enforce the
full component-entry schema (required fields, agent_affinity, exposed_interfaces,
depends_on referential integrity), `build.py` to inject the components table into
agent templates, and the AC parent-coverage hook to fail open on non-UTF-8 files —
so the component registry is trustworthy and no valid commit is blocked by a
binary-content decode error.

## Context

Extends the existing `check_components_integrity.py` hook (do NOT create a new
validator) and the `inject_config` phase of `build.py`/`build_phases.py`. All
eight ACs are pre-written and approved under
`docs/acceptance-criteria/ac-store/`. Follow the project error-handling policy
(fail-open on unexpected errors) and keep validation of the full
`components.json` under 1s.

## Acceptance Criteria

### ACS-300g-1 — Each backfilled component entry satisfies the minimum schema
```gherkin
Given docs/components.json receives a new component entry,
When the entry is validated by check_components_integrity.py,
Then it contains all required fields: id (snake_case string), name (string),
  type (infrastructure|utility|orchestration|coding|review|documentation|analysis),
  description (>=10 chars), status (active|reviewed|planned),
  primary_code (array of >=1 path string),
And detail_ref is either a valid path to an on-disk Markdown file or null.
```

### ACS-300g-2 — Existing component entries are preserved unmodified during backfill
```gherkin
Given docs/components.json already contains sync_platforms, build_pipeline, config_loader,
When new subsystem entries are added,
Then the pre-existing entries remain byte-for-byte identical (same values, same field order).
```

### ACS-300h-1 — Agent affinity field is present on every component entry
```gherkin
Given docs/components.json contains N component entries,
When a validator checks completeness,
Then every entry contains an agent_affinity field that is a JSON array (even if empty),
And no entry omits it or sets it to null.
```

### ACS-300i-1 — Interface descriptor schema is enforced on exposed_interfaces elements
```gherkin
Given a component entry includes an exposed_interfaces array,
When each element is validated,
Then every element has exactly four non-empty fields: name, type
  (file_contract|json_schema|function_signature|cli_command|hook_protocol|event|data_shape),
  path, shape,
And an element missing any field is rejected with an error naming the missing
  field and the component (report ALL missing fields in one pass, not fail-on-first).
```

### ACS-300i-2 — Components with no external interfaces have an empty array
```gherkin
Given a purely internal component,
When its entry is written,
Then exposed_interfaces is an empty array [] (never omitted or null),
And the validator rejects absent/null exposed_interfaces, requiring an explicit [].
```

### ACS-300j-1 — depends_on references only valid component IDs
```gherkin
Given a component entry has depends_on referencing other component IDs,
When the validator cross-references each element against all component IDs in the file,
Then valid references pass,
And any invalid reference is rejected with an error naming the invalid reference,
  the declaring component, and the list of available valid component IDs.
```

### ACS-300k-1 — build.py injects components data into agent templates via a placeholder
```gherkin
Given a template agent file contains the placeholder {{components_table}},
When build.py compiles the template,
Then the placeholder is replaced with a human-readable table (Markdown, sorted by
  component id) including at minimum id, name, type, description, agent_affinity,
And the compiled output contains zero occurrences of "{{components_table}}",
And injection does not break the existing inject_config placeholder system.
```

### ACS-100i-2-i — Hook fails open when a staged YAML file contains non-UTF-8 binary content
```gherkin
Given a staged .yaml file under docs/acceptance-criteria/ contains non-UTF-8 binary content,
When check_ac_parent_covered_by attempts to load and parse it,
Then the hook logs a WARNING naming the file path and the decode error,
And the hook returns exit code 0,
And the commit is NOT blocked by this hook.
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
