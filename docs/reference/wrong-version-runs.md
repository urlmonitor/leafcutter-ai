---
title: "Reference: Wrong-Version Runs"
description: "Lookup for the wrong-version runs every build route makes before it commits: which tests are in scope, which wrong versions run, every result word and stop reason, the put-back, the routes and the /build-epic backstop."
type: reference
status: active
created: 2026-10-23
last_updated: 2026-10-23
components:
  - testing_quality
  - build_orchestration
related_docs:
  - docs/reference/consumer-test-sweep.md
  - docs/testing/test-angles.md
  - docs/how-to/write-a-test-that-catches-the-wrong-version.md
  - docs/architecture/components/build-orchestration.md
  - docs/architecture/diagrams/c3-035-wrong-version-runner-components.md
  - docs/architecture/diagrams/c3-036-wrong-version-run-sequence.md
---

# Wrong-Version Runs

Lets a reader whose work was stopped with a report such as "drop the retry_due condition survived test_refresh_gate" look up what ran, what each result word means, whether it stops the work, and what to change.

A **wrong version** is a copy of the finished code altered in one plausible way, for example "drop the `retry_due` condition". A guarding test is **caught** when it fails under that wrong version and passes on the code as written. The runs are real `pytest` runs; no agent's claim about a result is read.

Terms used below. A **route** is one of the four ways a build runs (the fast lane, `/build-feature`, a single ticket, `/build-epic`); a **drive** is one run of a route. `--ac-ids` are the acceptance criteria (ACs) the work builds; their records are described in [AC schema](ac-schema.md). The **work key** names the work folder the writer fills. The **base ref** is the git ref the work began from.

Components and diagrams: [component diagram](../architecture/diagrams/c3-035-wrong-version-runner-components.md), [run sequence](../architecture/diagrams/c3-036-wrong-version-run-sequence.md).

---

## Scope: which tests are in scope

The runs cover the tests tagged `# covers: <ac-id>` (Python files only) for the `--ac-ids` given. Scope comes from each test's own `test_spec` entry in the [AC record](ac-schema.md), matched by test function name. Criteria, title and notes prose are never read.

| Case | Row | Detail or reason |
|---|---|---|
| Entry carries `must_catch` or `angle: discrimination` | In scope. | Runs as described below. |
| Any other covering test | `not_in_scope` | `not in scope for the runs: its test_spec entry names no wrong version and does not declare the discrimination angle` |
| Declared entry, no covering test of that name | `invalid` | `declared test not found: <name> is declared in test_spec but no covers-tagged test of that name exists` |
| A test whose node cannot be resolved | `invalid` | `the test file cannot be read: <error>` or `<function> resolves to <n> tests, not one` |
| An AC record cannot be read | Run stops. | reason `declared_ac_record_unavailable: <ids>` |
| No in-scope test and none declared | Not applicable. | outcome `wrong-version runs not applicable: no covering test declares a wrong version or the discrimination angle` |

Only in-scope tests run, selected by node id: one `pytest` run per wrong version, never the whole suite. Before any wrong version, the in-scope tests run once on the code as written. A test that is not `PASSED` there is `not_run` with `failing on the code as written (outcome <X>)`, and the verdict reason is `failing on the code as written`. With no source requirement (`--ac-ids` empty) the outcome is `wrong-version runs not applicable: no source requirement`.

## Which wrong versions run

| Wrong version | Runs for | Notes |
|---|---|---|
| Each `must_catch` name of a test's own entry | That test. | Declaration order. Names compare after trimming and case-folding. |
| A to-run-later extra | The test it names. | After the named versions. Never blocks; see [To-run-later extras](#to-run-later-extras). |
| `the fix undone` | Every in-scope test. | Always runs, last. |

The constant `ALIASES` in `_wvr_scope.py` is `{"revert the fix", "the fix undone"}`. An alias means the fix undone and is never sent to `test-breaker`. A test with `angle: discrimination` and no `must_catch` answers only for the fix undone.

**The fix undone** is prepared from git, never by an agent. The non-test files changed against `--base-ref` (`git diff --name-status --no-renames`) go back to their base content:

| Status | Handling |
|---|---|
| `M`, `D` | The path is restored to its base content. |
| `A` (created by the work) | Left in place, because deleting it would be a failure by absence. |
| Any other status | `invalid`: `wrong version could not be prepared: the change of <path> has status <S>, which cannot be undone` |
| No file to restore | `not_applicable`: `every changed non-test file is new (<n> created); the fix undone does not apply`. The same text, with `(0 created)`, appears when no non-test file changed at all. |

Files of the AC store are excluded. Test files are never altered by any wrong version. A path is a test file when it lies under the test root or a `tests/`, `unit_tests/`, `test/` or `__tests__/` folder, is named `test_*`, `*_test.py`, `*.test.ts`, `*.test.tsx` or `*.spec.ts`, or is `conftest.py`.

## Each test answers for its own names

A named version is held per test: a sibling's catch never covers another test. The fix undone runs every in-scope test and also carries a group rule: when no test fails under it, a row with test `""` is `survived` with `no test in scope failed under 'the fix undone'`. A test whose entry names an alias also answers for the fix undone on its own. **Caught** means the test failed under that wrong version by an assertion (the kind rule of `done_proof_kind_support` and `_kind_plugin`) and was `PASSED` on the code as written.

## Preparation

| Step | Command and output |
|---|---|
| 1. List | `wrong_version_writer.py list --ac-ids --ac-root --test-root --base-ref` prints `{owed: [{name, files, scope}], error}`. `scope` is `declared` or `derived`. A to-run-later extra also carries `blocking: false` and `origin: "to_run_later"`. |
| 2. Prepare | Agent `test-breaker` (tool `Read` only; never runs tests, never says what would be caught) replies `{work_key, entries: [{name, status: prepared or could_not_prepare, reason, replacements: [{path, old, new}]}], anomalies}`. |
| 3. Write | `wrong_version_writer.py write --work-key --reply -` writes `<git-dir>/leafcutter/work/<work-key>/alterations.json` and `copies/`, and prints `{written, manifest_path, error, entries, ignored_reply_names, preparer_anomalies}`. Exit 1 when it stops. |

Scope per name: `declared` is the union of `in_scope_files` over the entries naming it, minus test files. `derived` is the `A` and `M` paths plus untracked, non-ignored files against the base ref, minus test files and the AC store, sorted. A missing base ref stops the list with `the base ref "<ref>" does not exist, so the files the work changed cannot be worked out`. The work key must be one plain path segment.

Reasons the writer gives for a name it could not prepare (manifest `reason`): `no alteration returned`; `more than one alteration returned`; `old text found <n> times in <file>`; `old text not found in <file>`; `old text is empty in <file>`; `<path> is a test file`; `<path> is outside the repository`; `<path> is inside the version-control folder`; `<path> is not in scope for "<name>"`; `<path> not found`; `<path> is not UTF-8 text`; `malformed reply entry: <field>`; `no reason given`; or the preparer's own reason. One refused replacement refuses the whole name.

Reasons the writer stops (`error`): `the preparer's reply could not be read: <detail>` `the preparer reported failure: <blocker_summary>`, `the reply is empty` (inside the first), `the work key '<key>' is not one plain path segment`, and `internal error: <error>`.

## Result words

Each row of `results` is `{test, wrong_version, result, blocking, detail}`. `blocking` is false for `caught`, `not_in_scope` and `not_applicable`, true otherwise. `unfinished` marks results that leave the work unfinished.

| `result` | Blocking | Unfinished | Meaning and fixed detail text |
|---|---|---|---|
| `caught` | No | No | Failed by an assertion after reaching the code: `failed under '<wv>' by an assertion, after reaching the code`. |
| `survived` | Yes | No | `passed under '<wv>': the test did not notice it`. Stops the work. |
| `did_not_load` | Yes | Yes | `wrong version did not load: not a valid run`, suffixed `(the test file failed to collect)` or `(the failure was an import, name or attribute lookup)`. |
| `not_applied` | Yes | Yes | `wrong version not applied: it changes nothing`. The run is not made. |
| `invalid` | Yes | Yes | The run is not a valid test of the wrong version. Causes below. |
| `not_run` | Yes | Yes | No valid result: `the run was cut short (<timeout, crash, interrupted or unreadable>): <detail>`, `the test produced no result in this run`, `the test ended <OUTCOME>, neither passed nor failed`, the baseline row `the run on the code as written was cut short (<status>): <detail>` (reason `unfinished`), and the database and put-back rows. |
| `not_in_scope` | No | No | A test outside scope, or an unusable to-run-later note. |
| `not_applicable` | No | No | The fix undone has nothing to restore. |

`could_not_prepare` is not a row result. It appears only as the `result` of an `unfinished[]` entry (`{wrong_version, result, detail}`) whose detail starts with `wrong version could not be prepared`.

**Causes of `invalid`:**

| Cause | Detail |
|---|---|
| Manifest entry not prepared | `wrong version could not be prepared: <reason>` |
| Name without manifest entry | `wrong version could not be prepared: no entry in the alterations manifest`, plus ` (the alterations manifest is unreadable: <error>)` when the file could not be read. |
| Manifest file outside the name's scope | `not prepared: <path> is not in scope for "<name>"` |
| Manifest cannot be applied | `wrong version could not be prepared:` then `the manifest names a path outside the repository`, `the alteration would change a test file: <path>`, `the altered file does not exist as written: <path>`, `the altered copy of <path> cannot be read: <error>`, `the manifest entry names no file`, or `a file to alter cannot be read (<error>); nothing was altered`. |
| Fix undone cannot be undone | See the status table above, or `the fix undone could not be prepared from git: <error>`. |
| Derived scope cannot be worked out | `not prepared: <git or base-ref error>` |
| An AC record cannot be read | `declared_ac_record_unavailable: <ids>` (test `""`). |
| Test not found or not resolved | See [Scope](#scope-which-tests-are-in-scope). |
| Failure kind unknown | `the kind of the failure could not be determined from the run` |
| The suite put the correct code back | `the suite put the correct code back before the tests ran: <object> held the code as written`. See [Database tests](#database-tests). |
| Bad `--record` key (runner CLI) | `record: ticket key '<key>' is not one plain path segment` |

## Verdict and stop reasons

The runner prints one JSON object and exits 0 if and only if `gate_passed` is true: `{gate_passed, applicable, verified, outcome, reason, results, survivors, unfinished, non_blocking_survivors}`. `survivors` and `non_blocking_survivors` list `{test, wrong_version}`. `verified` means every owed run was validly made; it can be true while survivors stop the work, and it is not "passed". It can also be true on a not-applicable verdict that lists `not_in_scope` rows.

| `outcome` | When |
|---|---|
| `wrong-version runs passed: every wrong version was caught` | `reason` is null. |
| `wrong-version runs stopped the work: <reason>` | Any reason below except a stop message. |
| `wrong-version runs not applicable: no source requirement` | `--ac-ids` empty. `applicable` false, `gate_passed` true. |
| `wrong-version runs not applicable: no covering test declares a wrong version or the discrimination angle` | Nothing in scope. `applicable` false, `gate_passed` true. |

| `reason` | Stops the work because |
|---|---|
| `null` | Nothing stops it. |
| `survivor` | A blocking row is `survived`. Outranks `unfinished`. |
| `unfinished` | A blocking row is `did_not_load`, `not_applied`, `invalid` or `not_run`. |
| `failing on the code as written` | The baseline run failed. |
| `the code may still be altered: <path> <why>; the copy of the code as written is kept at <absolute path>` | The put-back failed. The outcome carries the same text. |
| `the database was not put back: <objects> still differs from the code as written` | The database put-back failed (`... could not be verified against the code as written` when unverifiable). |
| `declared_ac_record_unavailable: <ids>` | An AC record cannot be read. |
| `internal error: <error>` | The runner failed; recovery text is appended when the code may be altered. The outcome carries the same text, with no prefix. |
| `record: <error>` | With `--record`, the verdict record could not be written; `gate_passed` becomes false. The outcome is left as the runner printed it. |

## The finish command

`wrong_version_gate.py finish --work-key --reply - [--ac-ids] --ac-root --test-root --base-ref [--record]` is the one command a route runs before commit. Only `--reply -` (stdin) is supported. It prints `{gate_passed, stopped_at, sweep, writer, verdict}` and exits 0 if and only if `gate_passed` is true. Order: `consumer_sweep.py check`, then the writer's `write`, then the runner's `run`.

| Case | `gate_passed` | `stopped_at` | `sweep` / `writer` / `verdict` |
|---|---|---|---|
| Sweep check did not pass | false | `"sweep"` | sweep object / null / null. Neither writer nor runner is called. |
| Writer did not write a manifest | false | `"write"` | sweep / writer object / null. The runner is not called. |
| Runner ran | the verdict's `gate_passed` | `null` | all three objects. |
| With `--record`: invalid ticket key, the earlier `wrong_version.json` cannot be removed, or `--reply` other than `-` | false | `null` | all three null. |

**Route halts.** A halt payload carries `gate: "wrong_version_gate"`, `wrong_version_step` and `wrong_version_detail` (the parsed reply verbatim), and a message that starts `Wrong-version <step> step did not pass: <json>` and ends with a route-specific note (for example `No PR is opened.`, `No ticket was dispatched.`, `No phase agent was spawned.`). Two steps use their own message: `batch-serial-check` reads `This ticket owes wrong-version runs but its batch ran in parallel; no wrong-version step ran.`, and the `input-check` at the drive head of `/build-feature` and the single-ticket route reads `Wrong-version inputs are not plain values, no command was run: <json>`. Steps: `input-check` (not on the fast lane), `recover`, `list`, `finish`, and `batch-serial-check` (`/build-feature` and `/build-epic`). `/build-epic` also halts with `gate: "gate_verdict_marker"` and `marker_step` `input-check` or `open`, message `Gate-verdict marker <step> did not pass for <ticket path>: <json>. The ticket-supervisor was not dispatched.` The fast lane releases its claimed ACs on a halt.

## Put-back

Per run, the copies of the code as written and `journal.json` live in `<git-dir>/leafcutter/wrong-version-runs/<run-id>/`. The run id is `<YYYYMMDDTHHMMSS>-<pid>`; copies are named `copy-<n>-<file name>`. The journal is written durably before any file is altered. After each run every file is put back and compared byte for byte, the journal is closed by renaming it `journal.done`, and the folder is cleared. `git stash`, `git checkout` and `git restore` are never used.

Every `run` step starts with the same recovery. `wrong_version_runner.py recover` prints `{restored, ok, copy_dir, detail}`; a closed run folder is never restored. A timeout, crash or interruption puts the code back first and gives `not_run`. A hard kill leaves the journal open for the next invocation. A failed put-back stops the run, and no later wrong version runs.

**When the report says `the code may still be altered`:**

1. Commit nothing.
2. Run `python <scripts>/build_orchestration/wrong_version_runner.py recover` from the worktree.
3. When `ok` is false, compare the named file with the copy at the path the message gives.
4. Never delete the run folder while `ok` is false.
5. Re-drive the build.

## Database tests

A test is a database test only when its `test_spec` entry says `requires_db: true`. The runner calls `check_test_db(<repo root>)` once per run, and only when some in-scope test is a database test.

| Status | Rows of the database tests |
|---|---|
| `reachable` | Run. |
| `not_configured`, `invalid`, `config_error`, `check_failed` | `not_run` with `<status>: <message>`. |
| `unreachable` | `not_run` with `unreachable: the configured database could not be reached (testing_context.db_connection_test)`. |

Non-database tests still run. The catalogue check applies only when an alteration changes a `.sql` file and an in-scope database test runs. The plugin `_wvr_db_plugin`, loaded into the same single `pytest` run, installs the altered `CREATE [OR REPLACE] FUNCTION` / `PROCEDURE` definitions at session start, before any `setUpClass`. After each database test's call phase it reads `pg_proc.prosrc` on its own connection and compares the whitespace-normalised body.

| Catalogue held | Row |
|---|---|
| The wrong version | The row stands. |
| The code as written | `invalid`: the suite re-installed the correct code before the tests ran. Install from the source files the work changes. |
| Neither, unreadable, or no capture | `not_run` (`the catalogue held neither version of <objects>`, `the catalogue could not be read (<error>)`). |
| No difference | `not_run`: `the wrong version and the code as written are indistinguishable in the catalogue` |
| Objects not identifiable | `not_run`: `the database objects of <file> cannot be identified unambiguously` |
| No driver | `not_run`: `no PostgreSQL driver importable in the test interpreter (tried psycopg2, psycopg, pg8000)` |

The baseline installs the as-written definitions; when that fails the rows read `the code as written was not installed in the test database for this run: <why>`. Stop messages name objects, never an address. The address comes only from `resolve_test_db_address`; any address in a doc is the placeholder `postgresql://<user>:<password>@<host>:<port>/<database>`.

## To-run-later extras

The file `<git-dir>/leafcutter/to-run-later/<ac-id>.json`, written by `sql-test-writer`, has the shape `{ac_id, to_run_later: [{test, wrong_version, reason}]}`. Extras run and are reported, but every row has `blocking` false and a surviving extra goes into `non_blocking_survivors`, never `survivors`. An extra spelled like a `must_catch` name of the same test, or like the fix undone, stays the blocking named version. An unreadable file or entry, or an extra whose test is not a resolved in-scope test, gives one non-blocking `not_in_scope` row; nothing is dropped silently.

## Reading of runs

One reader, `pytest_outcome_reader`, is shared by done proof, the red-baseline reader, the runner (`_wvr_pytest`) and the sweep's runs. A `SUBFAILED` line makes its test `FAILED`; a test that failed in any sub-case is failed. Exit 1 with no parsed failing test is **inconclusive**. The runner folds parametrised cases per test; the worst wins.

| Reader | Inconclusive becomes |
|---|---|
| Wrong-version runner | `not_run`: `the run was cut short (unreadable): ...` (unfinished). |
| Done proof | The AC is not eligible: `could not verify <ac-id>: the run did not finish -- ...` |
| Red baseline | Neither red nor green. |
| Sweep | Reason `inconclusive`. |

## Routes

Every route calls the same CLIs with `--base-ref HEAD` through the executor `command-step-runner`, except the `/build-epic` list and finish steps, which the `ticket-supervisor` runs as its own Bash calls. The rule lives once, in Python; the workflow files and the skill copy only a thin dispatch.

| Route | File | Labels | Where it runs |
|---|---|---|---|
| Fast lane | `fast-lane-ship.js` | `fastlane-wv-recover`, `fastlane-wv-list`, `fastlane-wv-test-breaker`, `fastlane-wv-finish` | Phase `Wrong-Version Runs`, after Review, Changelog and Knowledge Routing, before Commit. Recover only when the workspace was reused. Work key is the target AC id. |
| `/build-feature` | `build-feature.js` | `bf-wv-recover`, `bf-wv-list`, `bf-wv-test-breaker`, `bf-wv-finish` | Recover once at the drive head when the worktree was reused. List, `test-breaker` and finish run before every commit dispatch. One ticket per chunk unless every ticket has an empty `source_ac`. |
| Single ticket | `build-ticket.js` | `bt-wv-*` (same four steps) | Recover on every drive, after the Worktree Guard. The sequence runs before every commit dispatch. |
| `/build-epic` | `build-epic.js`, skill `building-epics` §5.10 | `be-wv-recover`, `be-gate-marker-close-all`, `be-gate-marker-open`, `be-gate-marker-close` | Recover and close-all at the drive head; open and close around each `ticket-supervisor`. The supervisor runs list, `test-breaker` and `finish ... --record "<ticket_key>"` (§5.10.2) inside the commit lock before every commit spawn. One ticket per chunk when any ticket owes runs or its `source_ac` cannot be read. |

## The /build-epic backstop

Records live in `<git-dir>/leafcutter/gate-verdicts/<ticket-key>/`: `open.json` (the marker, with a `source_ac` snapshot), `red_baseline.json` and `wrong_version.json`. They are written only by the gate CLIs (`gate_verdict_records.py open` / `close`, and `--record`). The pre-commit hook `check-build-epic-gate-verdicts` blocks, with these words:

| Block message |
|---|
| `<key>: red-baseline verdict is missing` / `unreadable` (and `wrong-version verdict is ...`) |
| `<key>: <label> verdict did not pass: <why>` |
| `<key>: <label> verdict says not applicable but the ticket has a source_ac` |
| `<key>: <label> verdict says passed but its rows show a surviving wrong version: <names>` |
| `<key>: <label> record is for [ids] but the ticket's source_ac is [ids]` |
| `<key>: wrong-version verdict is out of date for the code as it now stands (<path>)` |
| `<key>: the marker has no readable source_ac, so the verdicts cannot be tied to the ticket` |
| `code is staged but no ticket file of an open marker is (<keys>); stage the ticket file being committed. ...` |

Remedy: re-run the gate, or stage the marked ticket file. Records and markers are never edited by hand. `git commit --no-verify` bypasses the hook.

## Consumer-test sweep

Before the runs, `finish` calls `consumer_sweep.py check` on every route, also with no `--ac-ids`. Full tables: [Consumer-test sweep](consumer-test-sweep.md).

- **Must be listed:** every edit to an existing test, fixture, helper, constant, import, top-level call, block or mark in an existing test file or `conftest.py`. The `test-writer` records the list once, after its last edit: `consumer_sweep.py record --work-key --test-root --base-ref HEAD`.
- **Counts as weakening:** a test that passed at the base and is now skipped, expected to fail (`XFAIL` or `XPASS`) or removed (`weakened`); fewer assertions, a looser comparison, a wider tolerance or an assertion made conditional or cut off by an early exit (`loosened`).
- **The one exit:** a `removed` entry with a note, for a test deleted with the code it tested. It excuses absence only, never a skip or an expected failure.
- **Reasons, in precedence order:** `unlisted`, `sweep list missing`, `weakened`, `loosened`, `inconclusive`. An internal error sets `error` and `passed` is false.

## If a run stops the work

No flag turns the runs off. Deleting `must_catch` names, narrowing `in_scope_files`, adding `skip` or `xfail` marks, and editing a manifest, list or record are weakenings, never fixes.

| Stop | What to do |
|---|---|
| `survived` | Strengthen the named test so it fails under that wrong version: assert the distinguishing value, use distinct fixture values (`retry_due` distinct from `refresh_due`), add a control row. Then re-drive. |
| `could_not_prepare` | The name describes code that does not exist or is too vague. Amend the AC's `must_catch` name or `in_scope_files` through the AC authoring path. |
| `did_not_load` | Re-drive so the version is prepared again. If it recurs, see Known limits. |
| `failing on the code as written` | Fix the code or the test first. |
| Database `not_run` | Configure `testing_context.db_connection_test` or install a driver. |
| Re-deploy `invalid` | Install the database objects from the source files the work changes. |
| Sweep stop | Undo the weakening, or hand the test back. |

## Known limits

| Limit | Source AC |
|---|---|
| The kind rule classifies by exception type, so a wrong version that makes a test raise `AttributeError` reads `did_not_load`. This errs safe. | TQ-500g-1-i |
| A re-deploy inside a test's own uncommitted transaction cannot be seen from the plugin's separate connection. | TQ-500g-2-i |
| A wrong version caught only in `setUpClass` or setup has no call-phase capture and reads `not_run`. | TQ-500g-2-i |
| The real PostgreSQL catalogue query is tested only against stand-in drivers, not in CI. Only `CREATE FUNCTION` / `PROCEDURE` objects are identified. | TQ-500g-2-i |
| `verified` can read true together with `applicable: false` when covering tests exist but none is in scope (known issue, filed). | — |
| In a shared-worktree parallel batch, a sibling's unlisted edit can stop another ticket's finish. | TQ-500g-3 |
| On `/build-epic` the backstop is bypassed by `--no-verify`. | TQ-500g-1-viii |

Sweep gaps left to `pr-reviewer` are listed on the [sweep page](consumer-test-sweep.md#known-limits).

---

## See Also

- [Consumer-test sweep](consumer-test-sweep.md) — the sweep's lists, checks and tables.
- [How to write a test that catches the plausible wrong version](../how-to/write-a-test-that-catches-the-wrong-version.md) — writing the guarding test.
- [Test angles](../testing/test-angles.md) — the discrimination angle.
- [AC schema](ac-schema.md) — `test_spec`, `must_catch`, `in_scope_files`, `requires_db`.
- [Build orchestration](../architecture/components/build-orchestration.md) — owner of the runner, writer, gate and sweep.
- `scripts/build_orchestration/wrong_version_runner.py`, `wrong_version_writer.py`, `wrong_version_gate.py`, `gate_verdict_records.py` — implementation.
- `templates/skills/building-epics/SKILL.md` §5.10 — the `/build-epic` instructions.
