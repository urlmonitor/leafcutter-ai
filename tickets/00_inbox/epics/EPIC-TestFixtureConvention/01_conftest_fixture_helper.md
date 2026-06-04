---
title: "Add tests/fixtures/ directory and load_fixture() conftest helper"
status: todo
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
  architect-review: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: needed
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

- [ ] architect-review
- [ ] test-writer
- [ ] python-coder
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request
- [ ] adr-author

## Comments

## Implementation Tasks

### adr-author
- [ ] Author ADR documenting the test-fixture convention: directory layout,
  load_fixture() signature, module-naming rule (stem minus test_ prefix),
  _shared/ convention, and agent-prompt enforcement policy.
  Target: `docs/architecture/adrs/ADR-NNN-test-fixture-convention.md` where
  NNN is next free number.

### python-coder
- [ ] Add `load_fixture(name: str) -> Any` to `tests/conftest.py`:
  - Import `json` and `Path` from `pathlib` at module top
  - Implementation: resolve `Path(__file__).parent / "fixtures" / f"{name}.json"`
  - Open with `encoding="utf-8"` and return `json.load(fh)`
  - Raise `FileNotFoundError` naturally (no try/except suppression)
- [ ] Create `tests/fixtures/_shared/.gitkeep` to establish the shared
  fixture directory in version control
- [ ] Verify `tests/fixtures/` is not excluded by `.gitignore`

### test-writer
- [ ] Add `unit_tests/commit_guardian/test_load_fixture_helper.py` with:
  - `test_load_fixture_returns_parsed_json` — creates a tmp fixture file,
    monkeypatches conftest's `__file__`, calls `load_fixture()`, asserts dict
  - `test_load_fixture_slash_maps_to_subdir` — fixture name with slash resolves
    to nested subdirectory
  - `test_load_fixture_missing_raises_file_not_found` — calls with non-existent
    path, asserts `FileNotFoundError` is raised

### documentation-expert
- [ ] Update (or create) `docs/testing/README.md` to include a "Fixture
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
