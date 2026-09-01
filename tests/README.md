# Tests

**Read [`unit_tests/README.md`](../unit_tests/README.md) before writing or changing a test
here.** It carries the falsifiability rules for this repository, and they apply to both test
roots without exception. This file only covers what is specific to `tests/`.

The short version of the neighbouring file, so you know whether you need it (you do):

- A passing test is not evidence until you know it can fail. Where no red baseline is
  possible — every **negative control**, every test asserting an *absence* — you owe a
  **mutation proof** instead.
- Mutate the copy the test **imports**. Commit-guardian modules exist twice, tests load the
  build output, and a mutation applied to `templates/` **silently does nothing and reports
  green** — indistinguishable from the dead test you are hunting.
- Fixture realism is not failure capability. Assert over emitted artifacts, never source
  text. Report per item, never one aggregate verdict.

---

## What lives here versus `unit_tests/`

Both roots are collected by the same `pytest.ini` and both run in CI under the single
required **Test suite (pytest)** check. The split is historical rather than principled, so
do not read a contract into it — check where a module's existing tests live and put yours
beside them.

Broadly, `tests/` holds the wider-scope suites: `tests/ac_store/`,
`tests/commit_guardian/`, `tests/knowledge/`, plus `tests/fixtures/` and a `conftest.py`.

## `tests/conftest.py` — blast radius

A root `conftest.py` applies to **every** test collected beneath it, and import or
`sys.path` manipulation there changes how unrelated modules resolve. That has produced
false greens before: a test passes because of a path inserted by a conftest three
directories up, and fails the moment it is run alone.

**Fix import problems in the test file, not in a shared conftest.** If a change to this
`conftest.py` is genuinely required, run the affected suites *both* ways — whole-root and
single-file — before believing either result.

## `tests/fixtures/` — build them with the project's own writer

Never hand-type a fixture for an artifact a tool produces. Use `yaml.safe_dump`, the signoff
SKILL's recipe, the real generator. A hand-typed fixture reproduced an indentation bias and
hid a parser no-op **on every real ticket** through seven green sign-offs.

## Running

```bash
python -m pytest tests/ -q                       # this root
python -m pytest unit_tests/ tests/ -q           # everything CI runs

AC_ENFORCE_STRICT=1 python -m pytest tests/ -q   # see the truth — read on
```

Two defaults that will mislead you, both set in `pytest.ini`:

- **`pytest_ac_enforcement` xfails failures belonging to not-done ACs.** A plain run
  **undercounts** and can exit 0 over real failures. Use `AC_ENFORCE_STRICT=1` when the
  count matters. It also breaks `mark_ac_done`'s own gate, so prefix the command rather than
  exporting the variable.
- **`--continue-on-collection-errors` is on.** A collection error does not stop the run and
  is easy to scroll past. Read the summary line, not just the exit code.

The `unittest discover` command this file used to give was stale — it pointed at a path that
does not exist from the repo root and bypassed both plugins above, so it silently ran a
different, weaker suite than CI does.
