---
title: "Harden AC-linkage test enforcement (TrustworthyTestGate code-review follow-ups)"
status: todo
components:
  - ac_store
  - testing_quality
created: 2026-07-08
depends_on: []
priority: low
change_target: code
risk_surface: internal
requires_diagram: false
requires_adr: false
tags:
  - code-review-followup
  - test-enforcement
files_touched:
  - scripts/ac_store/test_enforcement.py
  - scripts/ac_store/pytest_ac_enforcement.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Harden AC-linkage test enforcement (TrustworthyTestGate code-review follow-ups)

## Actor / Goal
In order to make the AC-status-gated test-enforcement gate robust against silent
data-shadowing and fragile tag parsing, we need to address the MEDIUM/LOW findings
from the EPIC-TrustworthyTestGate code review so that the gate cannot be quietly
weakened by a duplicate AC id, an unparsed `.yml` file, a docstring-embedded tag,
or a mis-categorised xfail outcome.

## Context
Follow-up to EPIC-TrustworthyTestGate (merged via PR #172, 2026-07-08). The epic's
core plugin was verified clean by a real-store behavioral spot-check and a full-suite
regression diff; the HIGH finding (H-1, CI `-x`) and one MEDIUM (M-1, silent
ImportError swallow) were fixed before merge. These are the remaining MEDIUM/LOW
findings, all localised to the two enforcement modules.

Not in scope: L-4 (CI pytest job is `continue-on-error: true`, so the gate does not
block merges) — already tracked separately as BP-1200b. L-2 (dead root `conftest.py`)
was resolved during the epic merge.

## Acceptance Criteria
- [ ] AC-1: `build_ac_work_status_cache` detects duplicate AC ids across the store and logs a WARNING naming the id and the files involved, instead of silently letting the last-sorted file win (which can shadow a `done` AC and silence a regression). (M-2a)
- [ ] AC-2: The AC-store loader globs BOTH `*.yaml` and `*.yml` so AC records written with the `.yml` extension are not silently ignored. (M-2b)
- [ ] AC-3: `extract_covers_tag` anchors the `# covers:` match to the start of a source line (ignoring `# covers:` prose inside docstrings) AND returns ALL tags when a test declares more than one, rather than honouring only the first. (M-3)
- [ ] AC-4: Enforcement warnings in `test_enforcement.py` and `pytest_ac_enforcement.py` are emitted via the project logger (WARNING level) rather than `print(..., file=sys.stderr)`. (L-1)
- [ ] AC-5: The not-done-AC failure downgrade uses pytest's native xfail mechanism (`outcome="skipped"` + `wasxfail`) so the outcome categorises correctly under `--junit-xml` and `-rx`, instead of the non-standard `report.outcome = "xfailed"`. (L-3)

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |
| AC-5 | | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] AC-1: add duplicate-id detection + WARNING in `build_ac_work_status_cache`
- [ ] AC-2: extend the AC-store glob to include `*.yml`
- [ ] AC-3: line-anchor the `# covers:` regex and return a list of tags; update `classify` callers to handle multiple tags
- [ ] AC-4: replace `print(..., file=sys.stderr)` with `logging.getLogger(__name__).warning(...)`
- [ ] AC-5: switch the downgrade to native xfail (`report.outcome = "skipped"`, set `report.wasxfail`)
- [ ] Tests: red-first coverage for each AC (duplicate-id store, `.yml` record, docstring-tag + multi-tag function, logger capture, junit/-rx categorisation)

## Risk & Safety
- Touches money? No.
- Touches data? No — reads the AC store and pytest reports only.
- Reversibility? Fully reversible; changes are localised to two enforcement modules with test coverage.
