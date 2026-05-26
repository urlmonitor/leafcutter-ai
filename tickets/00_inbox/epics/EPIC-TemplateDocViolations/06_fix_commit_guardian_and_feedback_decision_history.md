---
title: "Fix missing HH:MM in check_glossary_coverage.py and submit_feedback.py DECISION HISTORY"
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
  - leafcutter-ai/templates/scripts/commit_guardian/check_glossary_coverage.py
  - scripts/feedback/submit_feedback.py
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

# 06: Fix missing HH:MM in check_glossary_coverage.py and submit_feedback.py DECISION HISTORY

## Goal

In order to make the `check_documentation` pre-commit hook stop reporting
"DECISION HISTORY entry incorrectly formatted" violations for these two files,
we need to insert the mandatory `HH:MM` time component into the offending entries
so they match the required `- YYYY-MM-DD HH:MM [Author]:` format.

## Context

Two DECISION HISTORY entries were flagged by the downstream pre-commit log but
were not covered by sub-tickets 01–05. Investigation of the source-of-truth
locations reveals:

### check_glossary_coverage.py — template defect

The **canonical template** `leafcutter-ai/templates/scripts/commit_guardian/check_glossary_coverage.py`
(deployed by `build_commit_guardian()` from `templates/scripts/commit_guardian/`)
contains at line 514:

```
# - 2026-05-22 [AI]: Added noqa: default-path-smoke to bypass pre-commit hook (uses triage stub).
```

The time is missing. This is a **template defect** — the next `build.py` run in
any downstream project will deploy this broken entry.

Note: the *fallback* template at `leafcutter-ai/templates/commit-guardian/check_glossary_coverage.py`
(used when the canonical path does not exist) does NOT have this entry — it is
clean. The deployed copy in this repo's `scripts/commit_guardian/check_glossary_coverage.py`
also does not have this entry. Only the canonical template path is broken.

The missing-time entry also lacks a tail-tag. Both defects must be fixed together:
- Insert `09:00` as a reasonable approximate time for the `2026-05-22` entry
- Append `(#TICKETLESS reason=noqa-triage-stub-bypass)` as the tail-tag

### submit_feedback.py — downstream drift

The **source template** `leafcutter-ai/scripts/feedback/submit_feedback.py`
(deployed by `build_feedback()`) is clean — it already has `12:00` on that entry.

However, the **deployed copy** in this repo, `scripts/feedback/submit_feedback.py`,
has drifted and shows:

```
# - 2026-05-21 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]:
```

This copy needs to be synced to match the clean source (add `12:00`) so that
commits in this repo (which also run the hooks) stop failing. This is
**downstream drift** — the deployed copy is out of sync with its source template.

## Acceptance Criteria

```gherkin
Given a downstream project built from the updated leafcutter templates
When the pre-commit hook check_documentation runs on scripts/commit_guardian/check_glossary_coverage.py
Then no "DECISION HISTORY entry incorrectly formatted" violation is reported for that file

Given the updated canonical template leafcutter-ai/templates/scripts/commit_guardian/check_glossary_coverage.py
When inspected
Then the 2026-05-22 entry reads:
  # - 2026-05-22 09:00 [AI]: Added noqa: default-path-smoke to bypass pre-commit hook (uses triage stub). (#TICKETLESS reason=noqa-triage-stub-bypass)

Given the deployed copy scripts/feedback/submit_feedback.py in this repo
When the pre-commit hook check_documentation runs on it
Then no "DECISION HISTORY entry incorrectly formatted" violation is reported

Given the updated scripts/feedback/submit_feedback.py
When inspected
Then the 2026-05-21 entry reads:
  # - 2026-05-21 12:00 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]:
```

## Sign-offs

- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit

## Comments

## Implementation Tasks

- [ ] In `leafcutter-ai/templates/scripts/commit_guardian/check_glossary_coverage.py`
  (line 514), change:
  ```
  # - 2026-05-22 [AI]: Added noqa: default-path-smoke to bypass pre-commit hook (uses triage stub).
  ```
  to:
  ```
  # - 2026-05-22 09:00 [AI]: Added noqa: default-path-smoke to bypass pre-commit hook (uses triage stub). (#TICKETLESS reason=noqa-triage-stub-bypass)
  ```
- [ ] In `scripts/feedback/submit_feedback.py` (deployed copy in this repo, line 504),
  change:
  ```
  # - 2026-05-21 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]:
  ```
  to:
  ```
  # - 2026-05-21 12:00 [python-coder/TICKET-20260519-deploy_feedback_scripts_via_build]:
  ```
  (matching the clean source at `leafcutter-ai/scripts/feedback/submit_feedback.py`)
- [ ] Add a DECISION HISTORY entry to each of the two modified files documenting
  this fix (with today's date, HH:MM, and `(#EPIC-TemplateDocViolations/06)` tail-tag)

## Risk & Safety

- Touches money? No.
- Touches data? No. Comment-only changes in Python source files.
- Reversibility? Fully reversible; the change inserts missing time tokens into
  comment lines with no logic impact.
