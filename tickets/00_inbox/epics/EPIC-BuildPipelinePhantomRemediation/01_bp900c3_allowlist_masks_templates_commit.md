---
title: "Broken-ref guard: templates-commit action must win over allowlist for tracked-source-under-templates"
status: done
components:
  - build_pipeline
created: 2026-07-14
last_updated: 2026-08-17
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
source_ac: BP-900c-3
ac_coverage:
  - BP-900c-3
files_touched:
  - scripts/build_propagation_audit.py
  - unit_tests/test_build_tracked_source_guard.py
out_of_scope:
  # Belongs to ticket 05 (BP-1200b), not to this ticket. Both tickets close in the
  # same reconciliation commit, so the scope guard attributes every staged source
  # file to both; this declares the correct owner.
  - unit_tests/build_guards/test_ci_test_gate.py
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

### 2026-08-17 — scope-refresh review (status: ok)

**Closed as SUPERSEDED — the defect was fixed on `main` after this ticket was written.**

Verified independently by three reviewers (product-owner, business-analyst, it-po) and
re-checked directly against the tree:

- `scripts/build_propagation_audit.py::_suggest_action` now evaluates the
  `_PREFIXES_WITH_EXISTING_DEPLOY_PHASE` branch **before** the allowlist branch, returning
  `ACTION_COMMIT_UNDER_TEMPLATES` first. The reorder carries an inline comment naming
  BP-900c-3 and the `scripts/feedback/...` scenario as its rationale — i.e. the fix was
  made deliberately against this AC, not incidentally.
- `unit_tests/test_build_tracked_source_guard.py` carries `# covers: BP-900c-3` (x3) and
  `# covers: BP-900c-3-i` (x2), green under `AC_ENFORCE_STRICT=1`. The named proof test
  `test_ac_bp900c3_suggests_commit_when_dir_exists` calls `_suggest_action` directly — a
  real behavioural assertion, not a source grep.
- BP-900c-3-i (source-dir-absent → `ACTION_ADD_DEPLOY_PHASE`) did not regress.

No work remains. Driving this ticket would dispatch `test-writer` onto an already-green
suite, which is a TDD-order violation rather than a pass.

Residual: the AC row itself still read `work_status: not_started`; store reconciliation
is tracked separately with per-row evidence.
