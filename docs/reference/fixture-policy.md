---
title: "Reference: Fixture Authenticity Policy"
description: "Lookup reference for the fixture authenticity rules: which data kinds must use the real serializer, what fixture forms are rejected, and the round-trip requirement for parser and validator tests."
type: reference
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/how-to/real-artifact-fixtures.md
  - docs/architecture/adrs/ADR-007-test-fixture-convention.md
  - templates/agents/test-writer.md
---

# Fixture Authenticity Policy

Lookup reference for the fixture authenticity rules that govern how test inputs are produced in this repository. Use this document to determine whether a proposed fixture form is allowed or rejected, and what the correct alternative is.

---

## Rules Overview

| Rule | Applies to | Requirement |
|---|---|---|
| **Fixture Authenticity** | Any test needing serialized-format input | Fixture bytes must be produced by the real serializer, not hand-typed |
| **Round-trip** | Parser and validator tests | Serialize fixture to a temporary file on disk, read it back, assert on the re-parsed value |
| **Real-artifact behavioral check** | Parsers, validators, hooks, matchers | Feed at least one real on-disk artifact through the code path per tested code path |

**Canonical source:** `templates/agents/test-writer.md` §2h.2 — the authoritative rule, enforced in every `test-writer` invocation.

---

## Fixture Authenticity Rule

When a test needs input of a type that a tool serializes on disk — YAML tickets, AC files, JSON configs, or any structured artifact — the fixture MUST be produced by the real producer, not hand-typed as an inline literal.

### Serialized-format definition

A "serialized format" is any file type that a tool in this repository writes to disk as its primary output:

| Format | Real producer | Canonical invocation |
|---|---|---|
| YAML tickets / AC files | PyYAML | `yaml.safe_dump(data, stream)` |
| JSON configs | Python `json` module | `json.dumps(data, indent=<N>)` with the same `sort_keys` / `ensure_ascii` as the real writer |
| Markdown tickets | ticket-writer scripts | Read an existing on-disk file verbatim |
| Any other structured artifact | the tool that writes it | Use the tool's own output, or read an existing file verbatim |

### Allowed and rejected fixture forms

| Form | Status | Notes |
|---|---|---|
| `yaml.safe_dump(data, tmpfile)` — write, then read back | **Allowed** | Required for all YAML-format fixtures |
| `json.dumps(data)` with the same kwargs as the real writer | **Allowed** | Required for all JSON-format fixtures |
| Read an existing on-disk artifact verbatim | **Allowed** | Use when a real artifact exists in the repository |
| Hand-typed YAML or JSON string literal | **Rejected** | Never valid as a serialized-format fixture |
| Indented YAML where the real writer produces column-0 output | **Rejected** | Passes the test while hiding the bug; violates authenticity even if it parses |
| `yaml.safe_load("key: value")` on an inline string | **Rejected** | Bypasses the round-trip and does not catch serializer-bias bugs |

---

## Round-Trip Requirement (parsers and validators)

For any test that exercises a **parser** or **validator**, the fixture must travel the same I/O path the production system uses:

1. Build the input data as a Python dict or object.
2. Serialize it with the real serializer to a **temporary file on disk**.
3. Re-read the file from disk. Do not assert on the in-memory string from step 2.
4. Assert on the value obtained from the re-parse.

The disk write / disk read cycle may introduce encoding, newline, or whitespace differences that in-memory bytes do not have.

**Correct pattern:**

```python
import yaml
import tempfile
import pathlib

def test_parser_reads_real_yaml():
    # covers: BO-2500c-4
    ticket_data = {"files_touched": ["scripts/foo.py"], "status": "todo"}

    # Step 1 — serialize with the REAL serializer (yaml.safe_dump)
    # Produces column-0 dashes — the same format the real ticket writer produces.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.safe_dump(ticket_data, f)
        fixture_path = pathlib.Path(f.name)

    # Step 2 — round-trip: read BACK from disk, not from the in-memory string
    with open(fixture_path, encoding="utf-8") as f:
        parsed = yaml.safe_load(f)

    # Step 3 — assert on the round-tripped value
    assert parsed["files_touched"] == ["scripts/foo.py"]
```

**Rejected pattern:**

```python
# BAD — hand-typed YAML string. Indentation matches the author's mental model,
# not what yaml.safe_dump() produces. A parser that only handles column-0 dashes
# passes this test while being a complete no-op on every real artifact.
raw = """
  files_touched:
    - scripts/foo.py
  status: todo
"""
parsed = yaml.safe_load(raw)
assert parsed["files_touched"] == ["scripts/foo.py"]
```

---

## Scope — When This Rule Applies

Apply the Fixture Authenticity Rule when the test subject is any of:

- A **parser**: reads YAML, JSON, TOML, Markdown, or any structured text and extracts values.
- A **validator**: checks whether a file conforms to a schema or set of rules.
- A **hook**: receives a path and makes a pass/fail decision.
- Any code that processes a **serialized format** as its input, even simple ones.

Do **not** apply this rule for:

- Pure computation tests with no I/O: arithmetic, string transforms, list filtering, in-memory graph traversal.
- Tests that generate output and assert on the bytes produced — those test the serializer, not a downstream parser.

---

## Real-Artifact Behavioral Check

Round-trip tests with synthesized fixtures catch most serializer-bias bugs. Add an independent real-artifact behavioral check whenever the component's correctness on real data is the primary risk.

**What to do:**

1. Identify an existing on-disk artifact the code processes. For a ticket parser: use a real ticket from `tickets/`. For an AC validator: use a real AC YAML from `docs/acceptance-criteria/`. For a JSON config hook: use the deployed `commit_guardian.json`.
2. Feed that artifact through the real code path in a test that does not modify the artifact.
3. Assert on observable behavior, not on the artifact's content. Examples: "the parser does not raise, and the returned list is non-empty"; "the hook exits 0 on a valid ticket".

**Example:**

```python
import subprocess
import pathlib
import pytest

def test_parser_handles_real_ticket_without_error():
    # covers: BO-2500c-4
    # Use an actual on-disk ticket — the system wrote it, not the test author.
    real_ticket = pathlib.Path(
        "tickets/00_inbox/epics/EPIC-SomeEpic/01_some_ticket.md"
    )
    if not real_ticket.exists():
        pytest.skip("reference ticket not present in this worktree")

    result = subprocess.run(
        ["python", "scripts/parse_files_touched.py", str(real_ticket)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()  # at least one path was parsed
```

One real-artifact check per tested code path is sufficient.

---

## Rationale

**Why hand-typed fixtures are not sufficient:**

A hand-typed fixture always inherits the author's mental model of what the format looks like. When the author's model differs from the real serializer's output — different indentation, different quoting, different key order, different whitespace around colons — the fixture proves only that the code handles the author's approximation of the format, not the format the real system writes.

**Concrete precedent — EPIC-PhantomDoneFilesTouched (2026-07-07):**

The `files_touched` parser in a pre-commit hook required list-item dashes at column 0, the standard PyYAML `safe_dump` output. Every hand-typed fixture in the test suite used indented dashes (two spaces), matching the author's mental model of how YAML looks. Seven tickets signed off green. The hook was a total no-op on every real ticket in the repository.

The defect was invisible to the test suite because the fixtures reproduced the same bias that hid the bug. Only running the parser against an actual on-disk ticket file — produced by PyYAML itself — caught the column-0 vs indented-dash mismatch.

---

## Relationship to load_fixture() (ADR-007)

`load_fixture('<module>/<name>')`, defined in `tests/conftest.py` per [ADR-007](../architecture/adrs/ADR-007-test-fixture-convention.md), handles the **storage and retrieval** of fixtures whose data blob would push a test file past the 500-line ceiling.

The Fixture Authenticity Rule governs how the fixture **content is produced**. Both rules apply together:

1. Build fixture bytes with `yaml.safe_dump` / `json.dumps` (this document — Fixture Authenticity Rule).
2. If the data is large enough to push the test file over 500 lines, write it to `tests/fixtures/<module>/<name>.json` and load it with `load_fixture()` (ADR-007).
3. For parser/validator tests, always round-trip through a temporary file even when also using `load_fixture()` for the raw data.

---

## See Also

- `docs/how-to/real-artifact-fixtures.md` — task guide for authoring real-producer fixtures and round-trip tests, with step-by-step instructions.
- `docs/architecture/adrs/ADR-007-test-fixture-convention.md` — architectural decision for the `load_fixture()` helper and `tests/fixtures/` directory layout.
- `templates/agents/test-writer.md` §2h.2 — the authoritative rule enforced in every `test-writer` invocation.
