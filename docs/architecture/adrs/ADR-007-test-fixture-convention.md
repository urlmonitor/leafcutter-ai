---
title: "Test Fixture Convention: load_fixture() Helper and tests/fixtures/ Directory Layout"
type: adr
status: proposed
created: 2026-06-04
last_updated: 2026-06-04
components:
  - build_pipeline
related_docs:
  - docs/testing/README.md
related_code:
  - tests/conftest.py
  - tests/fixtures/_shared/.gitkeep
---

# ADR-007: Test Fixture Convention — load_fixture() Helper and tests/fixtures/ Directory Layout

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-06-04 |
| **Author** | adr-author (ticket 01_conftest_fixture_helper) |
| **Supersedes** | — |

## Context

Test files in the leafcutter-ai project currently inline large dicts, expected-output
blobs, and parametrize tables directly in the test source. This causes files to balloon
past the 500-line ceiling enforced by the line-count lint rule, makes test data hard to
review independently from test logic, and forces test authors to duplicate fixtures across
test modules.

The project's TDD workflow mandates test-first authoring. Without a shared fixture-loading
convention, each agent and human author invents their own approach: `json.loads` inline,
`open(Path(__file__).parent / ...)` hand-rolled, or literal dicts embedded in
`@pytest.mark.parametrize` decorators. The resulting divergence makes agent prompts harder
to write (they must account for multiple idioms) and causes line-count violations that
require remediation later.

This ADR establishes the canonical fixture convention that ticket 01
(`01_conftest_fixture_helper.md`) implements, and that tickets 02 (hook), 03 (agent
prompts), and 04 (orphan detection) build upon.

## Decision

The project WILL adopt the following test-fixture convention. All agents and human authors
MUST follow it when adding or migrating large test data.

### Directory layout

```
tests/
  conftest.py            ← load_fixture() helper lives here (sole canonical location)
  fixtures/
    _shared/             ← fixtures used by two or more test modules
    <module>/            ← module = test file stem minus the test_ prefix
                            e.g. tests/test_build_clean.py → fixtures/build_clean/
```

Rules:
- Every fixture file MUST be JSON, with the `.json` extension.
- The `tests/fixtures/` tree MUST NOT be excluded by `.gitignore`.
- Module subdirectory names MUST use the test file stem minus the `test_` prefix
  (e.g. `test_build_clean.py` → `build_clean/`).
- The `_shared/` directory is for fixtures consumed by two or more test modules.
  Module-specific fixtures MUST live in the module's own subdirectory.

### load_fixture() helper (canonical implementation)

```python
import json
from pathlib import Path
from typing import Any

def load_fixture(name: str) -> Any:
    """Load a JSON fixture by slash-separated path relative to tests/fixtures/."""
    path = Path(__file__).parent / "fixtures" / f"{name}.json"
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
```

This function MUST live in `tests/conftest.py` and nowhere else. Callers use
slash-separated paths:

```python
data = load_fixture("build_pipeline/valid_config")
# → tests/fixtures/build_pipeline/valid_config.json

shared = load_fixture("_shared/common_schema")
# → tests/fixtures/_shared/common_schema.json
```

The function MUST raise `FileNotFoundError` naturally when the path does not exist.
No try/except suppression is permitted (per the project error-handling policy).

### Agent-prompt enforcement

Agent templates (`test-writer`, `python-coder`) MUST instruct agents to:
1. Read `docs/testing/README.md` before authoring or migrating tests.
2. Use `load_fixture()` whenever a test blob would push the file past 500 lines.
3. Place new fixture files under `tests/fixtures/<module>/` (or `_shared/` when
   appropriate) following the naming rule above.

## Consequences

**Positive:**
- Test files stay within the 500-line ceiling because data blobs live in JSON files.
- Fixture data can be reviewed independently from test logic (separate file, separate diff).
- A single helper function eliminates the boilerplate of hand-rolling path resolution in
  every test file.
- Agent prompts for `test-writer` and `python-coder` can reference one canonical helper
  and one directory layout, reducing prompt divergence.
- The `_shared/` convention makes inter-module fixture reuse explicit and discoverable.

**Negative:**
- Adds one indirection step for developers reading tests: they must open the fixture file
  to see the data. For small, simple test data this is marginally worse than inlining.
- Fixture files must be maintained alongside tests; if a production schema changes,
  all JSON fixtures referencing the old schema must be updated.

**Operational:**
- A pre-commit hook (ticket 02) will detect fixture references that point to missing
  JSON files and block commits with orphan fixture calls.
- Agent-prompt updates (ticket 03) will propagate the convention to `test-writer` and
  `python-coder` templates automatically via `build.py`.

## Alternatives

1. **Module-level fixture factories (Python, not JSON).** Each test module could define
   a `fixtures` dict or factory function inline. Rejected because Python fixture factories
   are still counted toward the file's line total, defeating the 500-line ceiling
   enforcement. JSON externalisation is the only approach that removes the lines from
   the file entirely.

2. **pytest fixtures in conftest.py (not a load_fixture() helper).** Standard pytest
   fixtures auto-inject via function signature. Rejected because parametrize tables and
   expected-output blobs are not scope-aware and do not benefit from pytest's fixture
   lifecycle (setup/teardown). A simple `load_fixture()` call is less magic, easier to
   call from helper functions, and does not require the agent to understand fixture
   scoping rules.

3. **YAML instead of JSON.** YAML supports comments and multi-line strings, which could
   be useful for documenting fixture intent. Rejected because the standard library's
   `json` module loads JSON without any third-party dependency, keeping the helper to
   four lines. YAML would require `PyYAML` or `ruamel.yaml` as a dev dependency. The
   marginal expressiveness gain does not justify the dependency.

4. **Per-module conftest.py files.** Each test subdirectory could have its own
   `conftest.py` with module-local helpers. Rejected because it fragments the loading
   convention across multiple files, making agent prompts harder to specify ("check all
   conftest.py files") and requiring agents to decide where to add new helpers. A single
   root-level `conftest.py` is unambiguous.
