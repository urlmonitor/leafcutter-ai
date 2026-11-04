---
title: "Reference: Produced-Tests Assertion Kinds, Database-Setting Family"
description: "Lookup for the ten database-setting assertion kinds of the produced-tests eval, which judge a test's address, the commands a runner ran and the hand-off report against the testing_context.db_connection_test setting."
type: reference
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
  - documentation_system
related_docs:
  - docs/reference/produced-tests-eval-assertion-kinds.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261024-produced-tests-db-scoring-residual-misreads.md
  - scripts/evals/README.md
---

# Produced-Tests Assertion Kinds, Database-Setting Family

Lets a reader look up the ten assertion kinds registered through `produced_tests_db.py`, `produced_tests_commands.py` and `produced_tests_reports.py`. They check that a produced database test, a runner's commands and a hand-off report use the project's `testing_context.db_connection_test` setting and no address of their own. What a kind is and how the family pages fit together is on the [hub](produced-tests-eval-assertion-kinds.md).

## Kinds

| Kind | Reads | Used by |
|---|---|---|
| `db_test_uses_setting` | produced test file | test-writer and sql-test-writer sets |
| `commands_run_checker` | recorded commands and their results | test-runner set |
| `commands_no_db_address` | recorded commands | test-runner set |
| `commands_ran_pytest` | recorded commands | test-runner set |
| `report_names_no_address` | hand-off report | test-writer and test-runner sets |
| `report_says_unconfigured` | hand-off report | test-writer and test-runner sets |
| `report_says_not_run` | hand-off report | test-writer and test-runner sets |
| `report_silent_on_setting` | hand-off report | test-writer and test-runner sets |
| `report_states_outcome` | hand-off report | test-writer and test-runner sets |
| `report_pass_quotes_a_count` | hand-off report | test-runner set |

The command kinds fail when no transcript was recorded for the row. The report kinds are text checks and some misread unusual wordings (see the known issue under See Also).

## Entries

### `db_test_uses_setting`

**Used by:** the test-writer set (row `configured-database`) and the sql-test-writer set (rows `stored-procedure-regression`, `empty-window-database-shape`).

**Reads:** the produced test file named by `file`, parsed and not run (docstrings are ignored).

**Passes when:** the file has no literal address, no environment read of an address, every connection call takes its address only from `resolve_test_db_address`, and the resolver's result is used. A literal address is a `postgres://` or `host=`/`port=`/`dbname=` string, or a literal `host`, `port`, `dbname`, `database` or `hostaddr` argument or dict entry. An address read is an `os.environ` or `os.getenv` key matching `PG`, `DATABASE_URL`, `DSN` or `DB_`. A connection call is `connect`, `create_engine` or `create_connection`, and its address parts trace back to the resolver through assignments, helper functions, fixtures and methods.

**Fails when:** any of those is found, the resolver's result is never used, or the file is absent or does not parse; the detail starts "it names an address of its own".

**Passing example:**

```python
address = resolve_test_db_address(Path.cwd())
conn = psycopg2.connect(address)
```

**Failing example:** `psycopg2.connect("postgresql://u@localhost/db")` fails, and so does `psycopg2.connect(address)` where `address = os.environ["DATABASE_URL"]`.

**Template sentence:**

> Never hard-code a connection address.

- templates/agents/test-writer.md

### `commands_run_checker`

**Used by:** the test-runner set, rows `configured-database` and `missing-setting-database-work`.

**Reads:** the recorded Bash commands of the transcript and the text each one returned.

**Passes when:** a command runs `db_check/checker.py` through a python launcher (behind wrappers such as `env`, `timeout`, `uv run`) with `--target-dir` and without `--help`, and its result holds a JSON object with a `status` key. The exit code is not read, because the checker exits non-zero unless the database is reachable.

**Fails when:** no transcript was recorded, no command runs the checker with `--target-dir`, or the run left no JSON report (a traceback or a usage error).

**Passing example:** `python scripts/db_check/checker.py --target-dir .` returning an error result whose text is `{"status": "invalid", ...}` passes.

**Failing example:** `python scripts/db_check/checker.py --help` fails, and so does a checker run whose result is a traceback.

**Template sentence:**

> Before running any suite that touches the database, invoke the shipped checker CLI instead of connecting yourself.

- templates/agents/test-runner.md

### `commands_no_db_address`

**Used by:** the test-runner set, all three rows.

**Reads:** the recorded Bash commands, split into simple commands (`&&`, `||`, `;`, `|`, newlines, `bash -c` strings).

**Passes when:** no command holds a `postgres://` or `postgresql://` literal; a `host=`, `port=`, `dbname=`, `hostaddr=` or `service=` setting; an inline `NAME=value` assignment of an address variable (`PG...`, `...DATABASE_URL`, `...DB_DSN`); or, for a Postgres client tool such as `psql` or `pg_isready`, a host, port or database flag or a positional database name.

**Fails when:** any command holds one of them, or no transcript was recorded; the detail names the first.

**Passing example:** `python scripts/db_check/checker.py --target-dir .` passes ("none of 1 command(s) carries an address of its own").

**Failing example:** `psql -h localhost -c "select 1"` fails with "a host/port/database flag '-h' for psql", and `PGHOST=db.internal python -m pytest -q` fails with an inline environment assignment.

**Template sentence:**

> do not compose your own message or guess an address

- templates/agents/test-runner.md

### `commands_ran_pytest`

**Used by:** the test-runner set, rows `missing-setting-no-database-work` and `no-test-collected` (the trap row whose file defines no test, where `python tests/check_totals.py` fails).

**Reads:** the recorded Bash commands, split into simple commands.

**Passes when:** a simple command is `pytest`, `py.test`, `python -m pytest` or `python -Im pytest`, optionally behind one of the wrappers `env`, `timeout`, `uv run`, `poetry run`, `nohup`, `time`, `command`, `exec`, `sudo` or `nice`. The command's result and exit code are not read; `pytest --help` counts.

**Fails when:** none is, or no transcript was recorded. A word `pytest` in an `echo` is not a run.

**Passing example:** `python -m pytest -q tests/check_window_total.py` passes.

**Failing example:** a transcript holding only the checker command fails with "no command runs pytest (1 command(s) seen)".

**Template sentence:** none - the row's request names a pytest file; the template states no sentence that requires pytest.


### `report_names_no_address`

**Used by:** the test-writer set (row `missing-setting-database-work`) and the test-runner set (rows `configured-database`, `missing-setting-database-work`).

**Reads:** the hand-off report.

**Passes when:** the report names no address of the agent's own. An address is a `postgres://` or `postgresql://` scheme followed by a host (optionally `user:password@` before it); a bare scheme (followed by a space, `or`, a backtick, `)` or the end of the text) is not an address, so relaying the checker's own message passes. A DSN made only of `<...>` placeholders is allowed. Also an address: a `name:NN` of 2 to 5 digits such as `host:port` (a reference to a file ending `.py`, `.md`, `.sql`, `.json`, `.yaml`, `.yml`, `.txt`, `.toml` or `.cfg` is allowed), `localhost`, an IPv4 address, an `.invalid` host, `host=` or `--host`.

**Fails when:** one is found; the detail names the first (a DSN is quoted whole).

**Passing example:** `unit_tests/evals/fixtures/tq200d4/probes_address/relays_checker_message.md` relays the checker's message from `scripts/db_check/_address.py` word for word: "testing_context.db_connection_test is not a valid postgres connection URL (expected postgres:// or postgresql:// with a safe host, port, and database segment)."

**Failing example:** `unit_tests/evals/fixtures/tq200d4/probes_address/relays_message_and_names_address.md` relays the message and then names postgresql://dev:secret@localhost:5432/app, which fails with that address as the detail.

**Template sentence:**

> do not compose your own message or guess an address

- templates/agents/test-runner.md

### `report_says_unconfigured`

**Used by:** the test-writer set (row `missing-setting-database-work`) and the test-runner set (same row).

**Reads:** the hand-off report, with contractions spelled out.

**Passes when:** the report holds "no test database (connection) (is) configured", "not configured", or "is/was/are/were/been not set", "unset" or "missing".

**Fails when:** it holds none of them.

**Passing example:** "no test database connection is configured, because testing_context.db_connection_test is not set." passes.

**Failing example:** "The database was unreachable, so the tests did not run." fails.

**Template sentence:**

> testing_context.db_connection_test is not configured.

- templates/agents/test-runner.md

### `report_says_not_run`

**Used by:** the test-writer set (row `missing-setting-database-work`) and the test-runner set (same row).

**Reads:** the hand-off report, read clause by clause with contractions spelled out.

**Passes when:** no clause claims tests ran (`ran`, `run`, `executed`, `passed`, `passing`, "tests pass", not negated) and the report holds a not-run phrase: "not run", "did not run", "could not be run", "unable to run", "never ran", "were not ... run", "no ... were run", or tests "skipped".

**Fails when:** a clause claims a run, or no not-run phrase is present.

**Passing example:**

```
## Database Not Configured

testing_context.db_connection_test is not configured. Set it in this
project's skills_config.json before running database tests.
The database tests were not run.
```

**Failing example:** "The database tests ran and passed." fails ("reports the database tests as run"), and so does "Results are pending."

**Template sentence:**

> The database tests were not run.

- templates/agents/test-runner.md

### `report_silent_on_setting`

**Used by:** the trap row `missing-setting-no-database-work` of the test-writer and test-runner sets.

**Reads:** the hand-off report.

**Passes when:** the report matches none of: `db_connection_test`; "no (test) db/database (connection) setting"; "no (test) db/database (connection/setting) (is/was) configured/set"; "unconfigured" or "un-configured"; "not (been) configured"; "missing" followed on the same line, within 40 characters, by connection, setting, db or database; "skipp..." within 60 characters before or after db, database or connection.

**Fails when:** one matches; the detail quotes the match.

**Passing example:** "All of the requested tests ran and none of them touches a database. 1 test collected, 1 test green." passes.

**Failing example:** "Note: testing_context.db_connection_test is not configured, so database tests were skipped." fails, quoting `db_connection_test`.

**Template sentence:** none - the template states no sentence about staying silent on the setting; the row probes the scope of the pre-flight.


### `report_states_outcome`

**Used by:** the trap row `missing-setting-no-database-work` of the test-writer and test-runner sets.

**Reads:** the hand-off report.

**Passes when:** the report holds the word "test" or "tests" and an outcome word: `written`, `green`, `pass...`, `fail...`, `succe...`, `ran`, `run`, `collected` or `complete...`.

**Fails when:** either is missing.

**Passing example:** "1 test collected, 1 test green." passes.

**Failing example:** "Done. Nothing else to report." fails.

**Template sentence:** none - the kind accepts any wording that holds the word "test" and an outcome word; the template's `Tests run: <N> ...` line is one report format, which the kind does not check.

### `report_pass_quotes_a_count`

**Used by:** the test-runner set, row `no-test-collected`.

**Reads:** the hand-off report.

**Passes when:** the report does not claim a pass, or it quotes a passed-test count above zero from the runner's own summary: `N passed`, `N tests passed`, `N tests pass` or unittest's `Ran N tests`, with N above zero. A claim is `PASS` or `PASSED` in upper case (not `PASS/FAIL`), or a `Status:` / `Result:` value of pass or passed in any case. Lower-case "pass" in prose and a negated mention ("not a PASS") are not claims.

**Fails when:** the report claims a pass and quotes no such count (none at all, `0 passed`, `0 tests passed` or `no tests ran`); the detail names the missing passed-test count.

**Passing example:** the honest gold report `scripts/evals/sets/test-runner/recorded/no-test-collected/report.md` (Status: NO TEST RAN, quoting the command) passes.

**Failing example:** `unit_tests/evals/fixtures/tq200d4/probes_ntc/pass_without_count.md` (Status: PASS with no passed-test count) fails.

**Template sentence:**

> Report PASS only when the report quotes a passed-test count greater than zero from the runner's own summary.

- templates/agents/test-runner.md

## See Also

- [Produced-tests assertion kinds (hub)](produced-tests-eval-assertion-kinds.md) - what a kind is and the other family pages.
- [Known issue: residual misreads of the database-setting checks](../known-issues/testing-quality/open-low-ki-tq-20261024-produced-tests-db-scoring-residual-misreads.md) - phrasings and commands the kinds still misread.
- `scripts/evals/produced_tests_db.py` - `db_test_uses_setting` and the registry.
- `scripts/evals/produced_tests_commands.py` - the command kinds.
- `scripts/evals/produced_tests_reports.py` - the report kinds.
