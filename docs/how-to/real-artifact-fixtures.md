---
title: "How to author real-artifact fixtures and round-trip tests"
description: "How to produce test fixtures from the real serializer, round-trip them through an on-disk artifact, and add an independent behavioral check — and why hand-typed fixtures hide the bugs they are meant to catch."
type: how-to
category: how-to
status: active
created: 2026-07-21
last_updated: 2026-07-21
components:
  - build_orchestration
  - testing_quality
related_docs:
  - docs/reference/fixture-policy.md
  - docs/architecture/adrs/ADR-007-test-fixture-convention.md
  - docs/how-to/prove-ac-done.md
  - docs/architecture/components/build-orchestration.md
---

# How to author real-artifact fixtures and round-trip tests

This guide explains a single, mandatory rule: when you test a parser, validator,
hook, or any code that reads a serialized format, you must produce the test input
using the same serializer the real system uses — never by typing a string literal
by hand.

## 1. The defect blind-spot this rule prevents

During **EPIC-PhantomDoneFilesTouched** (2026-07-07), the `files_touched` parser
required list-item dashes at column 0 — the standard PyYAML block-sequence output.
Every hand-typed fixture in the test suite used indented dashes (two spaces in), which
matched the author's mental model of how YAML looks. Seven tickets signed off green.
The hook was a total no-op on every real ticket in the repository.

The defect was invisible to the test suite because the fixtures reproduced the same
bias that hid the bug. Only running the parser against an actual on-disk ticket file
— produced by PyYAML itself — caught the mismatch.

**The core problem:** a hand-typed fixture always inherits the author's mental model.
When the author's model differs from the real serializer's output (different
indentation, different quoting, different key order, different whitespace around
colons), the fixture proves only that the code handles the author's approximation of
the format — not the format the real system writes.

## 2. The Fixture Authenticity Rule

This rule is mandatory whenever a test needs input of a type that a tool serializes
on disk: YAML tickets, AC files, JSON configs, or any structured artifact.

### 2a. Produce the fixture bytes with the real serializer

**For YAML** — call `yaml.safe_dump()`, not a hand-typed YAML string.

**For JSON** — call `json.dumps()` with the same `indent`, `sort_keys`, and `ensure_ascii`
kwargs the real writer uses.

**For ticket files and other project artifacts** — use the actual tool output, or read
an existing on-disk artifact verbatim.

A hand-authored YAML/JSON/etc. string is **not** a valid fixture for a serialized format.

### 2b. Round-trip mandatory for parser and validator tests

For any test that exercises a parser or validator:

1. Produce the fixture bytes using the real serializer (rule 2a).
2. Write those bytes to a **temporary file on disk**.
3. Re-read the file from disk — do not assert on the in-memory bytes from step 1.
4. Assert on the value obtained from the re-parse.

The round-trip matters because the disk-write / disk-read path can introduce
encoding, newline, or whitespace differences that in-memory bytes do not have. The
re-read also exercises the exact code path the production system uses.

## 3. Concrete example: a round-trip fixture test

```python
import yaml
import tempfile
import pathlib


def test_files_touched_parser_reads_real_yaml():
    # covers: BO-2500c-4

    # --- Step 1: build input data as a Python dict ---
    ticket_data = {
        "files_touched": ["scripts/foo.py", "tests/test_foo.py"],
        "status": "todo",
    }

    # --- Step 2: serialize with the REAL serializer (yaml.safe_dump) ---
    # This produces column-0 dashes, not indented dashes. That is the format
    # the real ticket writer produces, and the format the parser must handle.
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False, encoding="utf-8"
    ) as f:
        yaml.safe_dump(ticket_data, f)
        fixture_path = pathlib.Path(f.name)

    # --- Step 3: round-trip — read BACK from disk, not from the in-memory string ---
    with open(fixture_path, encoding="utf-8") as f:
        parsed = yaml.safe_load(f)

    # --- Step 4: assert on the round-tripped value ---
    assert parsed["files_touched"] == ["scripts/foo.py", "tests/test_foo.py"]
    assert parsed["status"] == "todo"
```

What makes this correct:

- `yaml.safe_dump` produces the bytes PyYAML would produce in production (dashes at
  column 0, standard quoting, no extra indentation).
- The fixture is written to a real temporary file and read back — the same I/O path
  the production parser uses.
- The assertion is on `parsed`, the result of the round-trip, not on `ticket_data` or
  any in-memory string.

What would be wrong:

```python
# BAD — hand-typed YAML string. Indentation is the author's preference,
# not what yaml.safe_dump() produces.
raw = """
  files_touched:
    - scripts/foo.py
    - tests/test_foo.py
  status: todo
"""
parsed = yaml.safe_load(raw)
assert parsed["files_touched"] == ["scripts/foo.py", "tests/test_foo.py"]
```

This test passes even when the production parser only handles column-0 dashes,
because the fixture uses indented dashes and the fixture's own parser (yaml.safe_load
inline) is tolerant of both forms.

## 4. Adding an independent real-artifact behavioral check

Round-trip tests with synthesized fixtures catch most serializer-bias bugs. An
independent real-artifact behavioral check adds a second layer by feeding the code
path an artifact that was never touched by the test author at all — one the system
itself wrote.

**What to do:**

1. Identify an existing on-disk artifact of the type the code processes. For a ticket
   parser, use a real ticket file from `tickets/`. For an AC validator, use a real AC
   YAML from `docs/acceptance-criteria/`. For a JSON config hook, use the actual
   deployed `commit_guardian.json`.

2. Feed that artifact through the real code path (parser, validator, hook) in a test
   that does not modify the artifact.

3. Assert on observable behavior, not on the artifact's content. For example: "the
   parser does not raise, and the returned list is non-empty", or "the hook exits 0
   on a valid ticket".

**Example:**

```python
import subprocess
import pathlib


def test_parser_handles_real_ticket_without_error():
    # covers: BO-2500c-4
    # Use an actual on-disk ticket — the system wrote it, not the test author.
    real_ticket = pathlib.Path(
        "tickets/00_inbox/epics/EPIC-SomeEpic/01_some_ticket.md"
    )
    if not real_ticket.exists():
        import pytest
        pytest.skip("reference ticket not present in this worktree")

    result = subprocess.run(
        ["python", "scripts/parse_files_touched.py", str(real_ticket)],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip()  # at least one path was parsed
```

This test would have caught the EPIC-PhantomDoneFilesTouched defect on the first run
against any real ticket, regardless of what any fixture said.

**When to add this check:** add it whenever the component's correctness on real data
is the primary risk — parsers, validators, hooks, matchers. One real-artifact check
per tested code path is sufficient.

## 5. When this rule applies

Apply the Fixture Authenticity Rule whenever:

- The test subject is a **parser**: reads YAML, JSON, TOML, Markdown, or any
  structured text and extracts values from it.
- The test subject is a **validator**: checks whether a file conforms to a schema or
  a set of rules.
- The test subject is a **hook**: receives a path and makes a pass/fail decision.
- The test subject is any code that processes a **serialized format** as input — even
  if the serialization is simple.

You do **not** need to apply this rule for:

- Pure computation tests with no I/O: arithmetic, string transformation, list
  filtering, graph traversal on in-memory objects.
- Tests that generate output and assert on the bytes produced — those are testing the
  serializer itself, not a downstream parser.

## 6. Relationship to the load_fixture() helper (ADR-007)

`load_fixture('<module>/<name>')` (defined in `tests/conftest.py` per
[ADR-007-test-fixture-convention.md](../architecture/adrs/ADR-007-test-fixture-convention.md))
loads a JSON file from `tests/fixtures/`. That mechanism handles the **storage and
retrieval** of fixtures whose data blob would push a test file past the 500-line
ceiling.

The Fixture Authenticity Rule governs how the fixture **content** is produced. Both
apply together:

1. Build the fixture bytes with `yaml.safe_dump` / `json.dumps` (Fixture Authenticity Rule).
2. If the data is large enough to push the test file over 500 lines, write it to
   `tests/fixtures/<module>/<name>.json` and load it with `load_fixture()` (ADR-007).
3. For parser/validator tests, always round-trip through a temporary file even if you
   also use `load_fixture()` for the raw data.
