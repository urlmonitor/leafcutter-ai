---
title: "How to Verify the Shared Reference Layout Stays Read-Only"
description: "How to run and read the shared_layout_integrity guard so a test that dirties the shared deployed layout (TQ-600a-1) is caught and named, instead of silently corrupting every test that runs after it."
type: how-to
status: active
created: 2026-09-30
last_updated: 2026-09-30
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/testing/test-angles.md
  - docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml
related_code:
  - scripts/suite_performance/shared_layout_integrity.py
  - scripts/suite_performance/_shared_layout_integrity_compare.py
---

# How to Verify the Shared Reference Layout Stays Read-Only

Run and read the `shared_layout_integrity` pytest plugin's report to confirm the
session-shared deployed layout (TQ-600a-1) was never mutated by a
`shared_layout_reader`-marked test — and to find out exactly which test dirtied it
when it was.

## Prerequisites

- A checkout of this repo with `scripts/suite_performance/shared_layout_integrity.py`
  and its sibling `scripts/suite_performance/_shared_layout_integrity_compare.py`
  present (both are production files this guard is built on — the content-digest
  walk itself lives in the second file, not the first).
- Familiarity with the shared-layout fixture this guard protects: read
  "Tests must not spawn their own `build.py` — reuse a shared deployed layout" in
  `CLAUDE.md`, and the `shared_reference_layout` fixture in
  `scripts/suite_performance/pytest_shared_reference_layout.py`.
- `python -m pytest` runnable from the repo root (the guard relies on `pytest.ini`'s
  rootdir discovery to find the real `shared_layout_reader` marker registration).

## Steps

### Step 1 — Confirm the plugin is registered

The plugin is loaded two ways at once, and both matter for a real invocation:

1. It is registered in `pytest.ini`'s own `addopts`, alongside the pre-existing
   `-p scripts.ac_store.pytest_ac_enforcement` and
   `-p scripts.suite_performance.pytest_shared_reference_layout` entries — so it runs
   automatically on any real suite invocation that touches a
   `shared_layout_reader`-marked test, not only inside its own test suite.
2. Every test that exercises it ALSO passes an explicit `-p` override naming it.

Confirm the `addopts` registration:

```bash
grep -n "shared_layout_integrity" pytest.ini
```

Expected output includes:

```text
addopts = --continue-on-collection-errors -p scripts.ac_store.pytest_ac_enforcement -p scripts.suite_performance.pytest_shared_reference_layout -p scripts.suite_performance.shared_layout_integrity
```

Loading the same plugin twice (once via `addopts`, once via an explicit `-p`) is
idempotent — pytest de-duplicates by module identity — so passing the explicit `-p`
in Step 2 below is safe even though `addopts` already loads it.

### Step 2 — Run the suite with the guard active

Because the plugin is already in `addopts`, any normal run from the repo root
already carries the guard. To run it explicitly against a specific set of
`shared_layout_reader`-marked tests (for example while developing a new consumer
test), pass both plugins by name and run from the repo root:

```bash
LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT=/tmp/integrity_report.json \
  python -m pytest unit_tests/suite_performance \
  -p scripts.suite_performance.pytest_shared_reference_layout \
  -p scripts.suite_performance.shared_layout_integrity \
  -q
```

Setting `LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT` to a path is optional and
diagnostic only — the guard's pass/fail behavior at `pytest_sessionfinish` does not
depend on this variable being set; setting it additionally writes the full JSON
report described in Step 4 to that path.

### Step 3 — Read the terminal summary line

At the end of the run, `pytest_terminal_summary` prints exactly one of two lines:

```text
shared-layout-integrity: clean (N consumer(s) checked)
```

or, when a real difference was found:

```text
shared-layout-integrity: DIRTIED by <nodeid>
```

`<nodeid>` is the pytest node id of the first `shared_layout_reader`-marked test
whose post-teardown comparison newly reported a difference — the FIRST offender,
never overwritten by a later test even if that later test is also dirty. If the run
had zero `shared_layout_reader`-marked consumers, NEITHER line prints: printing
"clean" at zero consumers would misrepresent "nothing was checked" as "something was
checked and found untouched" (see Step 4 for why that distinction matters).

### Step 4 — Read the JSON report fields

If you set `LEAFCUTTER_SHARED_LAYOUT_INTEGRITY_REPORT` in Step 2, read the file it
names:

```bash
python -c "import json; print(json.dumps(json.load(open('/tmp/integrity_report.json')), indent=2))"
```

The report has these fields:

| Field | Type | Meaning |
|---|---|---|
| `compared_count` | `int \| None` | Size of the BASELINE record (the file count captured right after the first consumer's fixture setup). `None` only at zero consumers. `0` with `had_consumers: true` means the baseline was itself captured over an empty or absent root — a genuine failure, not a clean pass. |
| `added` | `list[str]` | Sorted relpaths present now but absent from the baseline. |
| `changed` | `list[str]` | Sorted relpaths present in both, with a different SHA-256 content digest. |
| `missing` | `list[str]` | Sorted relpaths present in the baseline but absent now. |
| `consumer_count` | `int` | Number of `shared_layout_reader`-marked tests that ran teardown this session. |
| `offending_test` | `str \| None` | The pytest node id of the first attributed offender, or `None`. |
| `files_ok` | `bool` | `False` when `compared_count == 0` (with consumers) OR any of `added`/`changed`/`missing` is non-empty. |
| `had_consumers` | `bool` | `consumer_count > 0`. |

Three shapes look similar but mean different things, and confusing them is exactly
the failure mode this guard exists to prevent:

- **Nothing to check** — zero consumers. `compared_count` is `None`, `had_consumers`
  is `False`, `files_ok` is `True`. This is a DELIBERATE non-failure: TQ-600a-1-i
  requires that no shared layout even be produced when nothing consumes it, so
  failing here would contradict that laziness guarantee.
- **Checked and found untouched** — one or more consumers, `files_ok` is `True`,
  `added`/`changed`/`missing` are all empty, and `compared_count` is a positive
  integer (the real file count that was compared).
- **Checked and found dirty** — `files_ok` is `False`, and either `offending_test`
  names the first offender (real mutation found) or `compared_count` is `0` despite
  `had_consumers: true` (the baseline itself was empty — a comparison over zero files
  reports nothing, by construction, on every path). This second sub-case mirrors a
  past incident in this repo where the AC-store validator globbed zero files and
  reported success for eight days; `files_ok` is written to catch that shape
  specifically, not just a non-empty diff.

## Verification

Deliberately dirty the layout in a throwaway consumer test and confirm the guard
catches it and names the test — the "can-fail proof" for this guard (see
[docs/testing/test-angles.md](../testing/test-angles.md) for why this step, not the
clean-run case, is the one that actually proves the comparison works):

```bash
mkdir -p /tmp/tq600a3_dirty_children
cat > /tmp/tq600a3_dirty_children/test_dirties_layout.py <<'EOF'
import pytest
from pathlib import Path


@pytest.mark.shared_layout_reader
def test_dirties_version(shared_reference_layout):
    root = Path(shared_reference_layout)
    (root / "VERSION").write_text("tampered", encoding="utf-8")
EOF
python -m pytest /tmp/tq600a3_dirty_children \
  -p scripts.suite_performance.pytest_shared_reference_layout \
  -p scripts.suite_performance.shared_layout_integrity \
  -q
echo "exit: $?"
```

Expected output: the exit code is non-zero, and the terminal summary contains a
line of the shape `shared-layout-integrity: DIRTIED by
<path>/test_dirties_layout.py::test_dirties_version` naming the exact test.

If you instead see `shared-layout-integrity: clean (1 consumer(s) checked)` or no
`shared-layout-integrity` line at all, see Troubleshooting.

## Troubleshooting

1. **No `shared-layout-integrity` line prints, clean or dirty.** The plugin was not
   loaded for this run. Confirm both the `pytest.ini` `addopts` registration (Step 1)
   and, if you passed an explicit `-p`, that the dotted path
   `scripts.suite_performance.shared_layout_integrity` is spelled correctly and the
   command was run with the repo root as `cwd` — pytest's rootdir/inifile discovery
   walks up from the given test path's own ancestry, not from the invoking shell's
   directory, so a test path outside this repo's tree will never find `pytest.ini`
   or the real `shared_layout_reader` marker registration.
2. **The deliberately-dirtied Verification step reports `clean` instead of
   `DIRTIED`.** The consumer test's marker is misspelled, or the fixture name is
   wrong — the guard only captures a baseline and attributes offenders for tests
   carrying the `shared_layout_reader` marker (registered in `pytest.ini`'s
   `[pytest] markers =` section) and requesting the `shared_reference_layout`
   fixture by name. A test that mutates the layout without that marker is invisible
   to this guard by design — it protects marked readers, not the whole tree.
3. **`compared_count` is `0` with `had_consumers: true`, and you did not expect a
   failure.** The baseline itself was captured over an empty or absent layout root —
   check that the shared deploy actually produced files before the first consumer's
   `call` phase ran (see `scripts/suite_performance/_shared_layout_producer.py` for
   the production side of that contract). This is treated as `files_ok: False`, not
   as a vacuous pass, on purpose.

## See Also

- [Test Angles — A Set-Cover Taxonomy for Proof of Done](../testing/test-angles.md) —
  the `failure` angle this guard's "deliberately dirty the layout" Verification step
  makes concrete: a comparison that only ever reports clean is worse than no
  comparison at all, because it licenses the very assumption it exists to test.
- `docs/acceptance-criteria/testing-quality/TQ-600-suite-feedback-latency/TQ-600a-3.yaml` —
  the acceptance criterion this guard implements.
- `scripts/suite_performance/shared_layout_integrity.py` — the session-level pytest
  plugin (hooks, registration, terminal summary) documented in this guide.
- `scripts/suite_performance/_shared_layout_integrity_compare.py` — the low-level
  content-digest walk (`capture_record` / `compare_record`) the plugin is built on;
  re-exported unchanged from `shared_layout_integrity.py`, so import from there
  rather than this private module.
- [Documentation Index](../INDEX.md) — auto-generated index of components, diagrams,
  and ADRs.
