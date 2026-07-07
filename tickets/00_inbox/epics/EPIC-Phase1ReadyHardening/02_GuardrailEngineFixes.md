---
title: "Commit-guardian import integrity + diagram_type enum + test-file exemption parity"
status: todo
components:
  - guardrail-engine
created: 2026-07-07
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/3
source_acs:
  - GE-103
  - GE-105
  - GE-110
ac_path: docs/acceptance-criteria/guardrail-engine/
files_touched:
  - templates/scripts/commit_guardian/diagram_type_validators.py
  - scripts/commit_guardian/diagram_type_validators.py
  - templates/commit-guardian/diagram_type_validators.py
  - scripts/commit_guardian/commit_guardian.json
  - templates/scripts/commit_guardian/commit_guardian.json
  - templates/commit-guardian/commit_guardian.json
  - templates/scripts/commit_guardian/check_exception_handling.py
  - unit_tests/commit_guardian/test_commit_guardian_imports.py
  - unit_tests/commit_guardian/test_check_exception_handling.py
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

# Commit-guardian import integrity + diagram_type enum + test-file exemption parity

## Actor / Goal

As the leafcutter package, we need every commit_guardian hook module to import
cleanly (so doc-frontmatter enforcement stays live), the diagram_type enum to
accept canonical values (data_flow, user_flow, agent_flow), and the test-file
exemption to exist in the canonical exception-handling guard — so consumer repos
don't silently lose enforcement or reject valid arch docs, and test files aren't
falsely flagged.

## Context

These are symptom fixes across the tracked commit-guardian source trees
(`scripts/commit_guardian/`, `templates/scripts/commit_guardian/`,
`templates/commit-guardian/`). The dead-SSOT architecture (diagram_types.json
never deployed; validator path off by one) is explicitly OUT OF SCOPE — fix the
effective runtime enum source only. All three ACs approved under
`docs/acceptance-criteria/guardrail-engine/`.

## Acceptance Criteria

### GE-103 — Every commit_guardian hook module imports cleanly
```gherkin
Given the commit_guardian package is deployed into a consumer project,
When the pre-commit pipeline imports check_doc_frontmatter.py (which imports
  frontmatter_validators, which imports diagram_type_validators),
Then the import succeeds without ModuleNotFoundError and doc-frontmatter
  enforcement runs rather than being silently disabled,
And a package import smoke test over every commit_guardian check_*.py and
  *_validators.py module imports each cleanly (a missing-module regression fails
  the suite instead of silently disabling a hook),
And "ModuleNotFoundError: No module named 'diagram_type_validators'" must not occur.
```
Note: recreate `diagram_type_validators` (lost in corruption merge 2c2aa22) in all
three tracked source dirs; module reads `leafcutter/config/diagram_types.json` as
canonical enum source and exposes `validate_diagram_type(fm)`.

### GE-105 — diagram_type enum accepts canonical values
```gherkin
Given a docs/**/*.md declaring a canonical diagram_type (data_flow, user_flow, agent_flow),
When check_doc_frontmatter runs validate_diagram_type during pre-commit,
Then the value is accepted because the effective enum source
  (commit_guardian.json -> doc_frontmatter.diagram_type_values runtime fallback) lists it,
And the legacy alias "dataflow" is still accepted (backward compatibility),
And "unknown diagram_type: agent_flow/data_flow" must not occur.
```
Note: add data_flow, user_flow, agent_flow; retain dataflow (deprecated alias) plus
context, container, component, sequence, erd, state, none.

### GE-110 — Test-file exemption present in the canonical exception-handling guard
```gherkin
Given templates/scripts/commit_guardian/check_exception_handling.py (canonical copy
  build.py reads first) and a staged test file (path contains tests/ or unit_tests/,
  OR basename matches test_*.py / *_test.py / conftest.py),
When the canonical hook runs,
Then the file is skipped before AST analysis (the GE-109a exemption) and emits no
  E722/BLE001/IO-001 violation,
And a non-test production .py file with the same violations is still blocked (exit 1),
  so the exemption never widens to production code.
```
Note: port is_test_file(path) + the main() short-circuit from the DEPRECATED
templates/commit-guardian/ copy into the canonical tree.

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
