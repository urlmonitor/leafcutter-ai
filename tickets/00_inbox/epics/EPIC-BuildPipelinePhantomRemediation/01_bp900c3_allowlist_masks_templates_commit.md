---
title: "Broken-ref guard: templates-commit action must win over allowlist for tracked-source-under-templates"
status: todo
components:
  - build_pipeline
created: 2026-07-14
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
source_ac: BP-900c-3
ac_coverage:
  - BP-900c-3
files_touched:
  - scripts/build_propagation_audit.py
  - unit_tests/test_build_tracked_source_guard.py
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

# 01: Allowlist branch masks the templates-commit suggestion

## Actor / Goal

As the build-time broken-reference guard, I want `_suggest_action` to return
`ACTION_COMMIT_UNDER_TEMPLATES` for a missing-or-untracked source that lives under a
directory whose deploy phase already exists — even when the path is also in the
external-dependency allowlist — so BP-900c-3 (the exact `scripts/feedback/submit_feedback.py`
scenario) is diagnosed truthfully instead of being told to "add to the allowlist".

## Remediation Context (audit 2026-07-14)

**Opposite behaviour + xfail-masked test.** In `scripts/build_propagation_audit.py`,
`_suggest_action` (around lines 245-288) checks `if missing_path in allowlist: return
ACTION_ADD_TO_ALLOWLIST` **before** the dir+phase-exists branch that returns
`ACTION_COMMIT_UNDER_TEMPLATES`. Because `scripts/feedback/submit_feedback.py` is present
in `EXTERNAL_DEPENDENCY_ALLOWLIST` **and** sits under a prefix in
`_PREFIXES_WITH_EXISTING_DEPLOY_PHASE`, the allowlist branch wins and the guard emits the
wrong action — the precise scenario BP-900c-3 targets (source is tracked-mirrorable under
`templates/scripts/`, not an external dependency). The genuine test
`unit_tests/test_build_tracked_source_guard.py::TestSuggestActionDirPresent::test_ac_bp900c3_suggests_commit_when_dir_exists`
is currently **RED** (it was xfail-masked, so it read green).

**Do: correct the branch ordering, don't rewrite.** Make the tracked-source-under-templates
branch (dir + deploy-phase exist) take precedence over the allowlist branch for paths that
are leafcutter-owned deploy-source (i.e. resolve the templates-commit suggestion first for
a path under `_PREFIXES_WITH_EXISTING_DEPLOY_PHASE`, falling back to the allowlist action
only for genuinely external paths). Preserve the three-field entry shape (missing_path,
referencing_template, suggested_action) and keep the BP-900c-3-i complementary branch
(source directory absent → `ACTION_ADD_DEPLOY_PHASE`) green — verify it does not regress.
Un-xfail and land the RED `test_ac_bp900c3_suggests_commit_when_dir_exists` as the proof.

## Acceptance Criteria

Resolves BP-900c-3 (verbatim Gherkin under
`docs/acceptance-criteria/build_pipeline/BP-900-deployment-completeness/BP-900c-3.yaml`).
Definition of done: for `scripts/feedback/submit_feedback.py` (allowlisted, dir+phase
present, source missing/untracked) the guard emits the commit-under-templates action, and
a test that names BP-900c-3 asserts it. BP-900c-3-i (source-dir-absent → add-deploy-phase)
stays green.

## Test Requirements

```yaml
tests:
  - name: test_ac_bp900c3_suggests_commit_when_dir_exists
    file: unit_tests/test_build_tracked_source_guard.py
    covers: [BP-900c-3]
    asserts: an allowlisted path under an existing-deploy-phase prefix returns ACTION_COMMIT_UNDER_TEMPLATES, not ACTION_ADD_TO_ALLOWLIST.
  - name: test_ac_bp900c3i_dir_absent_still_suggests_deploy_phase
    file: unit_tests/test_build_tracked_source_guard.py
    covers: [BP-900c-3]
    asserts: a path under an absent source directory still returns ACTION_ADD_DEPLOY_PHASE (no regression from the reorder).
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
