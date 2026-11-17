---
title: "Reference: Consumer-Test Sweep"
description: "Lookup for the consumer-test sweep: the list the test writer records, the check that runs before every commit, the reasons it stops the work, and the words of its weakened, loosened, removed and inconclusive items."
type: reference
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/reference/wrong-version-runs.md
  - docs/testing/test-angles.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/diagrams/c3-035-wrong-version-runner-components.md
  - docs/architecture/diagrams/c3-036-wrong-version-run-sequence.md
---

# Consumer-Test Sweep

Lets a reader look up what the sweep requires of an edit to an existing test, what the sweep check reports, and what each report means.

An existing test may be changed only after the `test-writer` has found the tests that depend on the changed code (the test's *consumers*) and said what it did to each. The check decides from the code at the base ref against the working tree and from the recorded lists, never from a claim that a list is complete. It is the first step of `wrong_version_gate.py finish` on every route; see [Wrong-Version Runs](wrong-version-runs.md#the-finish-command).

---

## Record

`consumer_sweep.py record --work-key <key> --test-root <path> --base-ref HEAD`, with the list on stdin: `{entries: [{file, test, status, note}]}`. Only the `test-writer` records, once, after its last edit. The work key is one plain path segment and not a reserved device name.

| Field | Type | Rule |
|---|---|---|
| `file` | string | Repo-relative POSIX path of the test file or `conftest.py`, inside the repo. |
| `test` | string | One-line symbol name; see [Name forms](#name-forms). |
| `status` | enum | `strengthened`, `unaffected` or `removed`. |
| `note` | string | Non-empty, one line: what was added, why it is unaffected, or why it was removed. |

| `status` | Meaning | Excuses an edit |
|---|---|---|
| `strengthened` | The test writer edited the symbol so it still proves something. | Yes, while the fingerprint matches. |
| `unaffected` | A consumer read and left unedited. | No. |
| `removed` | The work deleted the symbol together with the code it tested. | Absence only. |

The list is stored in `<git-dir>/leafcutter/work/<work-key>/consumer_sweep.json` as `{base, entries}`: the base commit, and each entry with a `fingerprint` the record step computes from the working tree (never supplied by the writer). The fingerprint is `absent` for a symbol that is not in the file. Output: `{recorded, path, error, entries}`; exit 0 only when `recorded` is true.

Record refusals (`error`, nothing is written): `the work key <key> is not one plain path segment`; `the work key <key> is a reserved device name`; `the list is not parseable JSON: <error>`; `the list needs an entries array`; `an entry is not an object`; `unknown status <value>`; `an entry needs a non-empty one-line note`; `an entry needs a one-line test name`; `<file> is not a canonical repo-relative POSIX path inside the repo`; `the list could not be written: <error>`; `internal error: <error>`.

### Name forms

| Form | Names |
|---|---|
| `test_name`, `Class::method` | A test function, a method. A `[param-id]` suffix names one parametrized case. |
| `name` | A class, fixture, helper or constant. |
| `import:<name>` | An import. |
| `call:<func>`, `expr:<kind>` | A top-level call, another top-level expression. |
| `set:<target>` | An assignment to an attribute or subscript. |
| `if:<header>`, `try`, `with:<items>`, `for:<target> in <iter>`, `while:<test>`, `match:<subject>` | A block. |
| File name | A test file that is not Python; it is compared as raw bytes. |

## Check

`consumer_sweep.py check --test-root <path> --base-ref <ref>` prints one object and exits 0 only when `passed` is true: `{passed, applicable, reason, unlisted, weakened, loosened, removed, inconclusive, error}`. `passed` is true when `reason` and `error` are both null. `applicable` is true when an edit, an inconclusive item or an in-scope run exists. "Existing" means present at `--base-ref`.

| Key | Item shape |
|---|---|
| `unlisted` | `{file, test}` of an edit no honoured entry excuses. |
| `weakened` | `{file, test, nodeid, what}` |
| `loosened` | `{file, test, what, detail}` |
| `removed` | `{file, test, nodeid, reason}`; `reason` is the entry's note. Reported, does not stop the work. |
| `inconclusive` | `{file, detail}`; `file` is null when the base ref or the changed files cannot be read. |

### Reasons, in precedence order

| `reason` | When |
|---|---|
| `unlisted` | An edit is unlisted and at least one honoured entry exists. |
| `sweep list missing` | An edit is unlisted and no entry is honoured at all. |
| `weakened` | A test that passed at the base is now skipped, expected to fail or gone. |
| `loosened` | A changed test asserts less, compares more loosely or tolerates more. |
| `inconclusive` | A comparison or a run could not be completed. |

An internal error sets `error` to `internal error: <error>` with `reason` null; `passed` is then false.

### Edits that need a list entry

The check compares every changed existing test file (status not `A`) at the base ref and now. Each top-level statement is a symbol. An edit is a symbol that changed (`changed`), vanished (`removed`) or is new and is not a test (`added`: a fixture, helper or constant). New tests need no entry. An entry excuses an edit only when it names the same file and symbol, has status `strengthened` or `removed`, and its fingerprint equals the symbol's current one. An `unaffected` entry and a stale fingerprint excuse nothing.

### `weakened`

Both sides run in separate `pytest` runs: the test files changed or deleted, widened to every test file in the test root below a changed `conftest.py` or config file (`pytest.ini`, `pyproject.toml`, `setup.cfg`, `tox.ini`). The base side runs in an export of the base ref. A test `PASSED` at the base is judged:

| `what` | Now |
|---|---|
| `skipped` | `SKIPPED`, or its whole module is skipped at collection. |
| `expected to fail` | `XFAIL` or `XPASS`. |
| `removed` | Absent from the run. |

### `removed` and the one exit

A test that is absent now is excused only by a `removed` entry with a note and an `absent` fingerprint for that file and test. The test then appears under `removed` with the note as its reason. The exit never excuses a skip or an expected failure.

### `loosened`

Found statically in the code of each changed test function, never by running it.

| `what` | `detail` form |
|---|---|
| `fewer assertions` | `<before> to <after>` |
| `comparison loosened` | `<form> became <form>` or `<form> removed`, one fragment per strict comparison lost. |
| `tolerance widened` | `rel <before> to <after>` or `abs <before> to <after>` on a `pytest.approx` pair. |
| `assertion now conditional` | `under <if, while, for, match, try, function, lambda or class>` |
| `assertion after an early return` | `return` |
| `assertion after an early skip` | `pytest.skip(...)`, `self.skipTest(...)`, `raise SkipTest` or `raise unittest.SkipTest` |
| `assertion after an early xfail` | `pytest.xfail(...)` |

### `inconclusive`

| `detail` |
|---|
| `<file> is not UTF-8 text: <reason>` |
| `<file> could not be read at the base ref, so its edits cannot be told` |
| `<file> does not parse: <message> (line <n>)` |
| `the base ref "<ref>" or the changed files could not be read: <error>` |
| `the files at the base ref could not be listed: <error>` |
| `the base ref <sha> could not be exported for the base run: <error>` |
| `the <base or working-tree> run of <file> did not finish: <detail>` |
| `<file> did not collect in the <base or working-tree> run` |

A contradictory run (exit 1, no identifiable failed test) reads as a run that did not finish; see [Reading of runs](wrong-version-runs.md#reading-of-runs).

### Which lists are honoured

The check reads every list under `<git-dir>/leafcutter/work/*/`. A list that cannot be read excuses nothing. A list is honoured at its own base commit. A list recorded at an earlier base is still honoured after the base moves on, for the entries whose file no commit in between touched, when the recorded base is an ancestor of the current one. Any git failure, or an unrelated base, leaves the entries unhonoured.

---

## Known limits

The sweep does not catch these; they are left to `pr-reviewer` (TQ-500g-3, TQ-500g-3-iii):

- a widened expected literal under the same operator;
- a dropped `match=` on `pytest.raises`, or a broadened `raises(Exception)`;
- a wider `places` or `delta` on `assertAlmostEqual`;
- a non-strict comparison made looser (`>= 1` to `>= 0`);
- a weakened fixture or helper (listed, but not compared);
- a tolerance that is not a plain number at the base;
- exits outside the closed list (`sys.exit`, `pytest.exit`, `pytest.importorskip`, a helper that skips);
- `with contextlib.suppress(AssertionError)`;
- an assertion that already had a guard gaining another.

Accepted strictness: merged asserts and a renamed asserted variable also stop the work.

---

## See Also

- [Wrong-Version Runs](wrong-version-runs.md) — the runs that follow the sweep check, and the `finish` command that calls it.
- [Test angles](../testing/test-angles.md) — the discrimination angle the sweep protects.
- `scripts/build_orchestration/consumer_sweep.py` and `_cs_*.py` — implementation.
- `templates/agents/test-writer.md` "Existing-Test Sweep" — what the test writer does and records.
