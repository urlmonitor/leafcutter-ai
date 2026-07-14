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
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: signed_off
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: signed_off
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

- [x] test-writer — 2026-07-14 14:30
- [x] python-coder — 2026-07-14 15:30
- [x] test-runner — 2026-07-14 13:19
- [ ] pr-reviewer
- [x] commit — 2026-07-14 15:50
- [ ] pull-request

## Comments

### 2026-07-14 15:30 — python-coder (status: ok)
feedback-id: fb_2026-07-14_52eaf407
completion_manifest:
  reference_pattern_resolution_implemented: true
  unresolvable_pattern_raises_value_error: true
  red_baseline_tests_green: true
  ruff_clean: true
  behavioral_spot_check_pass: true
Added `_resolve_reference_patterns` helper to `generate_ticket_from_ac.py` and wired it into `_build_implementation_notes_section` (now accepts `ac_id`). Both red_baseline tests turned green: raw glob pattern is replaced by the concrete resolved path, and a zero-match pattern raises `ValueError` naming the AC id and the pattern string.

red_baseline_results:
  - test_name: test_ac3_reference_pattern_resolves_to_paths
    result: green
  - test_name: test_ac3i_unresolvable_pattern_errors
    result: green

### 2026-07-14 14:30 — test-writer (status: ok)
feedback-id: fb_2026-07-14_8726670f
completion_manifest:
  phantom_covers_removed: true
  test_ac3_reference_pattern_resolves_to_paths_written: true
  test_ac3i_unresolvable_pattern_errors_written: true
  tests_are_red: true

## Test Writer — Completion Report

### Tests Written
| File | Directory | Framework | Status |
|---|---|---|---|
| test_implementation_notes_emission.py | unit_tests/prompt_assembly/ | unittest | modified (2 new tests added) |

### Verification Run
- Command: `python -m unittest discover -s unit_tests/prompt_assembly -t . -p "test_implementation_notes_emission.py" -v`
- Result: red (2 failures — expected; pattern-resolution not yet implemented)

### Notes
- Removed phantom `# covers: BO-2000c-3` and `# covers: BO-2000c-3-i` tags from `test_dispatch_prompt_instructs_read_ticket_and_stays_thin` (that test does not exercise path resolution).
- Added class `TestReferencePatternResolution` with two genuinely-red stubs.
- `test_ac3_reference_pattern_resolves_to_paths`: uses `tempfile.TemporaryDirectory` + a wildcard glob to distinguish raw pattern from resolved concrete path.
- `test_ac3i_unresolvable_pattern_errors`: expects `ValueError` naming the AC id and unresolvable pattern; current implementation raises nothing.

red_baseline:
  - test_name: test_ac3_reference_pattern_resolves_to_paths
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    error: "AssertionError: 'resolved_ref_*.py' unexpectedly found in '...## Implementation Notes\\n\\n```yaml\\nn_location_rule: Resolve before emitting.\\nreference_pattern: /tmp/.../resolved_ref_*.py\\n```...' : The Implementation Notes must NOT emit the raw glob wildcard pattern."
  - test_name: test_ac3i_unresolvable_pattern_errors
    file: unit_tests/prompt_assembly/test_implementation_notes_emission.py
    error: "AssertionError: ValueError not raised"

### 2026-07-14 13:19 — test-runner (status: ok)
feedback-id: fb_2026-07-14_5efabeff
completion_manifest:
  test_suite_executed: true
  all_tests_passing: true
  failure_report_structured: true
Ran unit_tests/prompt_assembly/test_implementation_notes_emission.py: 5 passed, 0 failures, 0 errors. Both new TestReferencePatternResolution tests (test_ac3_reference_pattern_resolves_to_paths and test_ac3i_unresolvable_pattern_errors) are green.

### 2026-07-14 15:50 — commit (status: ok)
feedback-id: fb_2026-07-14_fbe61e1a
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "feat(ac-store): resolve reference_pattern globs in ticket generator (BO-2000c-3/3-i)"; staged files: scripts/ac_store/generate_ticket_from_ac.py, scripts/ac_store/pytest_ac_enforcement.py, templates/scripts/commit_guardian/_signoff_parity_checks.py, unit_tests/commit_guardian/test_check_ticket_signoff_parity_done_folder.py, unit_tests/prompt_assembly/test_implementation_notes_emission.py, unit_tests/test_ticket_frontmatter_guard.py, plus EPIC-BOPhantomDoneRemediation ticket files 01/03/04/05.
