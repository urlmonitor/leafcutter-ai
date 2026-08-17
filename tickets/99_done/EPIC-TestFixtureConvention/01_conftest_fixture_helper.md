---
title: "Add tests/fixtures/ directory and load_fixture() conftest helper"
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: medium
phase: "Phase 1"
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - tests/conftest.py
  - tests/fixtures/_shared/.gitkeep
  - docs/testing/README.md
agents:
  architect-review: signed_off
  test-writer: signed_off
  python-coder: signed_off
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: signed_off
  adr-author: signed_off
  architecture-diagram-author: not_needed
  explanation-author: not_needed
  how-to-author: not_needed
  reference-author: not_needed
  user-surface-smoker: not_needed
requires_documentation:
  - how_to
---

# 01: Add tests/fixtures/ directory and load_fixture() conftest helper

## Actor / Goal

In order to keep test files within the 500-line line-count ceiling and to
separate data concerns from test logic, we need to establish a canonical
`tests/fixtures/<module>/` directory structure and a `load_fixture()` helper
in `tests/conftest.py`, so that agents and human authors have a shared
convention for externalising large test data blobs.

## Context

Tests in the leafcutter-ai project currently inline large dicts, expected-output
blobs, and parametrize tables directly in test files. This causes files to balloon
past 500 lines and makes the data hard to review independently from the test logic.

This ticket establishes the convention foundation that tickets 02 (hook), 03
(agent prompts), and 04 (orphan detection) all build upon.

### Directory convention

```
tests/
  conftest.py            ← load_fixture() helper lives here
  fixtures/
    _shared/             ← fixtures used by multiple test modules
    <module>/            ← <module> = test file stem minus test_ prefix
                            e.g. tests/test_build_clean.py → fixtures/build_clean/
```

### load_fixture() helper (canonical implementation)

```python
def load_fixture(name: str) -> Any:
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
```

Callers use slash-separated paths: `load_fixture("build_pipeline/valid_config")`
which resolves to `tests/fixtures/build_pipeline/valid_config.json`.

### ADR note

This ticket introduces a cross-project convention that binds test authors and
agent prompts to a shared structural contract. An ADR should document: the
directory layout, the load_fixture() function signature, the module-naming
rule (stem minus `test_` prefix), and the `_shared/` shared-data convention.

## Acceptance Criteria

```gherkin
Given tests/conftest.py has been updated
When load_fixture("build_pipeline/valid_config") is called
Then it returns the parsed JSON content of tests/fixtures/build_pipeline/valid_config.json

Given tests/fixtures/_shared/ exists
When a test imports load_fixture("_shared/common_schema")
Then it returns the parsed JSON at tests/fixtures/_shared/common_schema.json

Given a fixture path that does not exist on disk
When load_fixture("nonexistent/path") is called
Then a FileNotFoundError is raised with the missing path in the message

Given the docs/testing/README.md is reviewed
When the fixture convention section is read
Then it documents the directory layout, the load_fixture() signature,
 And the module-naming rule (test file stem minus test_ prefix)
```

## Sign-offs

- [x] architect-review — 2026-06-04 10:05
- [x] test-writer — 2026-06-04 10:10
- [x] python-coder — 2026-06-04 10:15
- [x] documentation-expert — 2026-06-04 10:20
- [x] pr-reviewer — 2026-06-04 10:25
- [x] commit — 2026-06-04 10:30
- [x] pull-request — 2026-06-04 10:35
- [x] adr-author — 2026-06-04 10:00

## Comments

### 2026-06-04 10:00 — adr-author (status: ok)
feedback-id: fb_2026-06-04_62d0adcf
completion_manifest:
  adr_file_created: true
  all_sections_present: true
  status_set: true
Authored ADR-028-test-fixture-convention.md at docs/architecture/adrs/; all five required sections present (Status, Context, Decision, Consequences, Alternatives). Handoff file written to tickets/.pending/adr_handoff.json. ADR-028 is the next free number (ADR-006 was highest on main).

### 2026-06-04 10:05 — architect-review (status: ok)
feedback-id: fb_2026-06-04_afaa2e85
completion_manifest:
  blast_radius_assessed: true
  impact_classified: true
  architectural_note_written: true
Blast-radius analysis: 3 files touched (tests/conftest.py, tests/fixtures/_shared/.gitkeep, docs/testing/README.md), 1 component (build_pipeline), no Alembic migration, no hypertable change, no public API change, no ADR contract change. Classification: SMALL — all threshold criteria below the large bar. No escalation to architect-review-deep needed. Design note: purely additive; no existing test files altered, no module boundary crossed, no contract changes. ADR-028 already authored. No diagrams needed (documentation/convention change, no new data flow or service boundary).

### 2026-06-04 10:10 — test-writer (status: ok)
feedback-id: fb_2026-06-04_019d312d
completion_manifest:
  tests_written: true
  tests_cover_all_acs: true
  tests_are_red: true
Wrote 3 unit tests in unit_tests/commit_guardian/test_load_fixture_helper.py: test_load_fixture_returns_parsed_json, test_load_fixture_slash_maps_to_subdir, test_load_fixture_missing_raises_file_not_found. Tests are red (failing) until python-coder creates tests/conftest.py with load_fixture(). All three Acceptance Criteria scenarios are covered. Monkeypatches conftest.__file__ to allow isolated testing without touching the real filesystem layout.

### 2026-06-04 10:15 — python-coder (status: ok)
feedback-id: fb_2026-06-04_4dc76d16
completion_manifest:
  load_fixture_implemented: true
  gitkeep_created: true
  gitignore_verified: true
  tests_green: true
Created tests/conftest.py with load_fixture(name: str) -> Any per ADR-028 spec: imports json and Path, resolves Path(__file__).parent / "fixtures" / f"{name}.json", opens with encoding="utf-8", raises FileNotFoundError naturally (no suppression). Created tests/fixtures/_shared/.gitkeep. Verified .gitignore has no fixtures/ exclusion. All 3 unit tests green (pytest 3 passed in 0.18s).

### 2026-06-04 10:20 — documentation-expert (status: ok)
feedback-id: fb_2026-06-04_c15514a1
completion_manifest:
  fixture_convention_section_added: true
  directory_layout_documented: true
  load_fixture_signature_documented: true
  module_naming_rule_documented: true
  shared_vs_module_guidance_documented: true
  agent_requirements_noted: true
Updated docs/testing/README.md with a "Fixture Convention (ADR-028)" section covering: directory layout with module-naming table, load_fixture() signature with usage examples, _shared/ vs module-specific guidance table, agent requirements (test-writer and python-coder must read this file before authoring tests), and cross-reference links to ADR-028 and the implementation files.

### 2026-06-04 10:25 — pr-reviewer (status: ok)
feedback-id: fb_2026-06-04_0e3b2e70
completion_manifest:
  acs_covered: true
  implementation_quality: true
  tests_verified: true
  documentation_reviewed: true
  no_regressions: true
All four Acceptance Criteria are covered: load_fixture() returns parsed JSON (test_load_fixture_returns_parsed_json, test_load_fixture_slash_maps_to_subdir), slash-path maps to subdir (test_load_fixture_slash_maps_to_subdir), missing path raises FileNotFoundError (test_load_fixture_missing_raises_file_not_found), docs/testing/README.md has Fixture Convention section. Implementation is clean: no bare-except, FileNotFoundError unblocked per error-handling policy, encoding="utf-8" on open, type hint present. ADR-028 complete with all 5 sections. 3 unit tests green (pytest 3 passed in 0.18s). No regressions introduced.

### 2026-06-04 10:30 — commit (status: ok)
feedback-id: fb_2026-06-04_6473cda5
completion_manifest:
  files_staged_explicitly: true
  commit_succeeded: true
  lock_acquired_and_released: true
Staged 7 files explicitly by path (no git add .). Committed as 773f4bf on branch EPIC-TestFixtureConvention: ADR-028, tests/conftest.py, tests/fixtures/_shared/.gitkeep, docs/testing/README.md, unit_tests/commit_guardian/test_load_fixture_helper.py, tickets/.pending/adr_handoff.json, ticket sign-offs. Lock acquired before staging and released after successful commit.

### 2026-06-04 10:35 — pull-request (status: ok)
feedback-id: fb_2026-06-04_7f628a1a
completion_manifest:
  branch_pushed: true
  pr_opened: true
Pushed EPIC-TestFixtureConvention branch to origin and opened PR #44 at https://github.com/urlmonitor/leafcutter-ai/pull/44. Title: "feat: add tests/fixtures/ convention and load_fixture() conftest helper (ADR-028)".

## Implementation Tasks

### adr-author
- [x] Author ADR documenting the test-fixture convention: directory layout,
  load_fixture() signature, module-naming rule (stem minus test_ prefix),
  _shared/ convention, and agent-prompt enforcement policy.
  Target: `docs/architecture/adrs/ADR-NNN-test-fixture-convention.md` where
  NNN is next free number.

### python-coder
- [x] Add `load_fixture(name: str) -> Any` to `tests/conftest.py`:
  - Import `json` and `Path` from `pathlib` at module top
  - Implementation: resolve `Path(__file__).parent / "fixtures" / f"{name}.json"`
  - Open with `encoding="utf-8"` and return `json.load(fh)`
  - Raise `FileNotFoundError` naturally (no try/except suppression)
- [x] Create `tests/fixtures/_shared/.gitkeep` to establish the shared
  fixture directory in version control
- [x] Verify `tests/fixtures/` is not excluded by `.gitignore`

### test-writer
- [x] Add `unit_tests/commit_guardian/test_load_fixture_helper.py` with:
  - `test_load_fixture_returns_parsed_json` — creates a tmp fixture file,
    monkeypatches conftest's `__file__`, calls `load_fixture()`, asserts dict
  - `test_load_fixture_slash_maps_to_subdir` — fixture name with slash resolves
    to nested subdirectory
  - `test_load_fixture_missing_raises_file_not_found` — calls with non-existent
    path, asserts `FileNotFoundError` is raised

### documentation-expert
- [x] Update (or create) `docs/testing/README.md` to include a "Fixture
  Convention" section documenting:
  - Directory layout (`tests/fixtures/<module>/` and `tests/fixtures/_shared/`)
  - The `load_fixture()` function signature and usage example
  - The module-naming rule (test file stem minus `test_` prefix)
  - When to use `_shared/` vs module-specific subdirectories
  - Noting that agents (test-writer, python-coder) are required to read this
    file before authoring tests

## Risk & Safety

- Touches money? No.
- Touches data? No — adds new files and updates one existing conftest.
- Reversibility? High — `load_fixture()` is purely additive. Existing tests
  are unaffected. The directory is an empty scaffold until tests migrate.
