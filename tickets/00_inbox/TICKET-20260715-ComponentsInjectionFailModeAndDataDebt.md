---
title: "components_table injection fail-mode decision (ACS-300k-1-i/-ii) + components.json empty primary_code debt"
status: todo
components:
  - build_pipeline
  - ac_store
created: 2026-07-15
depends_on: []
priority: medium
requires_diagram: false
requires_adr: true
files_touched:
  - scripts/build_phases.py
  - docs/components.json
  - docs/acceptance-criteria/ac-store/ACS-300-component-governance/ACS-300k-1-i.yaml
  - docs/acceptance-criteria/ac-store/ACS-300-component-governance/ACS-300k-1-ii.yaml
  - unit_tests/test_build_components_table.py
agents:
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: needed
  architecture-diagram-author: not_needed
complexity: standard

---

# components_table injection fail-mode decision + components.json data debt

## Context

Surfaced by the EPIC-Phase1ReadyHardening AC audit + test-backfill (PRs #223, #252,
#288, #292). Two residual items, both beyond the original audit scope, deferred here.

## Part A — ACS-300k-1-i / ACS-300k-1-ii: fail-soft vs fail-hard (needs a decision)

`_build_components_table()` in `scripts/build_phases.py` currently **soft-fails** when
`docs/components.json` is missing or malformed: it returns a placeholder string
(`"*(components.json not found)*"` / `"*(components.json parse error)*"`) and lets the
build continue, emitting the compiled agent files.

The two L3 edge-case ACs require the **opposite** (fail-hard):
- **ACS-300k-1-i** — missing `components.json` → build.py exits non-zero with
  `"docs/components.json not found -- required for {{components_table}} injection"`,
  and **no** partially-compiled agent files are written.
- **ACS-300k-1-ii** — invalid JSON → build.py exits non-zero, error names the parse
  error + path, no partial output.

These are currently `NOT_IMPLEMENTED` (the code does the opposite). This is a genuine
product/design decision, not a mechanical fix:

- **Option 1 — enforce hard-fail** (satisfy the ACs as written): make injection abort
  the build on missing/invalid `components.json`, with no partial output. Downside: a
  single typo in `components.json` breaks every build.
- **Option 2 — keep soft-degrade + revise the ACs**: the intentional graceful
  degradation may be the better product behavior; if so, rewrite ACS-300k-1-i/-ii to
  specify the soft-fail contract (placeholder note + WARNING log + build continues) and
  add tests for that.

**architect-review + adr-author**: record the decision as an ADR (hence `requires_adr`).
Then implement the chosen behavior and add real tests. ACS-300k-1 (parent) stays `todo`
until its children are resolved (its happy-path injection is already covered by
`unit_tests/test_build_components_table.py`).

## Part B — components.json empty `primary_code` data debt

`check_components_integrity.validate_component_minimum_schema` requires `primary_code`
to hold ≥1 path string. Five entries currently have an empty array (surfaced when
`unit_tests/commit_guardian/test_check_components_minimum_schema.py::test_all_current_entries_pass_minimum_schema`
was un-skipped in PR #292 — it is currently `xfail` pending this fix):

- `ac_driven_dev`
- `persona_management`
- `stakeholder_delivery`
- `ux_prototyping`
- `infrastructure`

Populate each entry's `primary_code` with its real source path(s), then flip the xfail
back to a hard assertion in that test file.

## Acceptance Criteria

- [ ] AC-1: An ADR records the components_table injection fail-mode decision (hard-fail vs soft-degrade), with rationale.
- [ ] AC-2: `scripts/build_phases.py` injection behavior matches the ADR decision, covered by tests for the missing-file and invalid-JSON cases.
- [ ] AC-3: ACS-300k-1-i and ACS-300k-1-ii are reconciled to the decision — either implemented + `work_status: done`, or their criteria rewritten to the soft-fail contract and then satisfied + done.
- [ ] AC-4: All 5 listed `components.json` entries have non-empty `primary_code` with real paths; `test_all_current_entries_pass_minimum_schema` is a hard assertion (xfail removed) and green.

## Risk & Safety

- Touches money? No.
- Touches data? Edits `docs/components.json` (registry) — additive field population; no destructive change.
- Reversibility? Fully reversible (config + hook-behavior edits, ADR).
- Part A changes build failure behavior — the ADR + tests gate it; verify no legitimate build regresses.

## Comments
