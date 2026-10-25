---
title: "KI-TQ-20261024-produced-tests-db-scoring-residual-misreads — the TQ-200d-4 database-setting checks still misread some commands, report wordings and test shapes, so a live test-runner or test-writer score can be falsely red or green"
description: "low — a pr-review of the TQ-200d-4 produced-tests scoring left residual misreads, accepted for now. commands_no_db_address reads psql <<EOF / psql < file.sql as a positional database, applies LIBPQ_RE to the whole command text (pytest -k \"host=x\", grep \"port = \", echo \"host=foo\"), and misses PowerShell $env:PGHOST=. The report checks read README.rst:10, tests:12, line:42, 3.11.2.5 and \"does not use localhost\" as addresses, miss \"were not attempted\", fail \"passed? No — they were not run\", flag \"Skipped 1 slow test about the connection pool\" and reject \"Tests OK\". db_test_uses_setting taints flow-insensitively, matches DB_SCHEMA / GPG_KEY as address keys, counts assert 'host=' not in x as a literal, and does not check ConnectionPool / create_pool. The checker-run check rejects python -m db_check.checker and -t . and excludes only --help. On a live timeout only the direct claude child is killed, and only the last 300 characters of stdout are kept. Recorded gold scoring is unaffected."
type: reference
category: reference
status: active
created: '2026-10-24'
last_updated: '2026-10-24'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261024-eval-harness-cannot-launch-claude-on-windows.md
---

# KI-TQ-20261024-produced-tests-db-scoring-residual-misreads — the database-setting checks still misread some phrasings

> Filed 2026-10-24. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. Each misread needs a particular phrasing, command or test shape. The recorded
  gold rows score correctly; a live test-runner or test-writer run that happens to use one of these
  shapes can be scored falsely red or falsely green.
- **Status:** open, no AC. Accepted for now after the TQ-200d-4 pr-review.
- **Occurrences:** 1 (the TQ-200d-4 pr-review, 2026-10-24; found by reading the code, not seen in a
  live run).
- **First seen:** 2026-10-24 · **Last seen:** 2026-10-24
- **Where** (line numbers in the TQ-200d-4 work as staged on `fast-lane/tq-200d-b`, on top of
  `ef43e33ea`; the four modules are new in that work):

### `commands_no_db_address` (`scripts/evals/produced_tests_commands.py`)

| Misread | Site | Cause |
|---|---|---|
| `psql <<EOF` and `psql < file.sql` are flagged as a positional database | `_positional_database` :215-221, called from `_pg_problem` :229 | The first token that does not start with `-` is taken as the database name, so `<<EOF` and `<` count. Tokens starting with `<` should be ignored. |
| `pytest -k "host=x"`, `grep -n "port = " f.py` and `echo "host=foo"` are flagged as a libpq address | `LIBPQ_RE` :34, applied in `_command_problem` :237 | The regex runs over the whole command text before the command is split, so any `host=` / `port =` anywhere in the line counts, whatever program it belongs to. |
| PowerShell `$env:PGHOST=...` is not flagged | `ENV_ADDRESS_RE` :35, checked per token at :240 | The pattern is anchored at the start of the token and knows only POSIX `NAME=value`; a `$env:` prefix never matches. |

### Report checks (`scripts/evals/produced_tests_reports.py`)

| Misread | Site | Cause |
|---|---|---|
| `README.rst:10`, `pytest.ini:3`, `run.sh:5` read as `host:port` | `HOST_PORT_RE` :35, `FILE_SUFFIXES` :36, `_address_in` :77-79 | Only the suffixes in `FILE_SUFFIXES` are excused as `file:line`; `.rst`, `.ini`, `.sh` and others are missing. |
| `tests:12 passed` and `line:42` read as `host:port` | `HOST_PORT_RE` :35 | Any word followed by `:` and 2-5 digits matches. |
| A version string such as `3.11.2.5` reads as an IPv4 address | `ADDRESS_RE` :37-38 | `\d{1,3}(?:\.\d{1,3}){3}` matches any four dotted digit groups. |
| "does not use localhost" reads as an address | `ADDRESS_RE` :37-38 | `\blocalhost\b` matches with no regard to negation. |
| "were not attempted" is not read as not-run | `NOT_RUN_RE` :24-28, used in `report_says_not_run` :102 | The wording set has no `attempted` (nor similar verbs). |
| "…passed? No — they were not run" fails the not-run check | `CLAUSE_RE` :20, `_claims_run` :54-59, `report_says_not_run` :99-101 | The clause split after `?` leaves "…passed?" as its own clause, which reads as an un-negated claim that tests ran. |
| `report_silent_on_setting` is false for "Skipped 1 slow test about the connection pool" | `MISSING_SETTING_RE` :40-45, `report_silent_on_setting` :106-110 | `skipp\w* … connection` within 60 characters counts as a warning about the missing setting. |
| `report_states_outcome` rejects "Tests OK" | `OUTCOME_RE` :46, `report_states_outcome` :113-116 | `OK` is not in the outcome word set. |

### `db_test_uses_setting` (`scripts/evals/produced_tests_db.py`)

| Misread | Site | Cause |
|---|---|---|
| `dsn = resolve_test_db_address(...); dsn = 'other'; connect(dsn)` passes | `Taint` :97-167, `_visit` :148-155 | Taint is a set of names that only grows, over the whole file, with no order; a later reassignment to a literal does not clear it. |
| An environment read of `DB_SCHEMA` or `GPG_KEY` counts as an address read | `ENV_KEY_RE` :28, used in `_env_reads` :79 | The pattern is unanchored: `DB_` and `PG` match anywhere in the key. |
| `assert 'host=' not in x` counts as a literal address | `ADDRESS_STRING_RE` :24, applied in `_literal_addresses` :49 | Every non-docstring string constant matching `host=` counts, including one used only in an assertion. |
| An unresolved variable passed to `ConnectionPool(...)` or `create_pool(...)` passes | `CONNECT_NAMES` :27, checked in `_connect_problems` :174 | Only `connect`, `create_engine` and `create_connection` are treated as connection calls. |

### Checker detection (`scripts/evals/produced_tests_commands.py`)

| Misread | Site | Cause |
|---|---|---|
| `python -m db_check.checker ...` is not a checker run | `_is_checker_run` :176-182 (:179) | Only a script run (`kind == "s"`) whose path ends in `db_check/checker.py` counts. |
| `-t .` is not accepted for the target directory | `_is_checker_run` :181 | Only `--target-dir` and `--target-dir=` are recognised. |
| A run with another non-run flag (anything but `--help` / `-h`) still counts | `HELP_FLAGS` :44, `_is_checker_run` :182 | Only the help flags are excluded. |

### `invoke_with_transcript`, live path only (`scripts/evals/produced_tests_transcript.py`)

| Problem | Site | Cause |
|---|---|---|
| On timeout only the direct `claude` child is killed | `subprocess.run(..., timeout=timeout)` :105-106 | `subprocess.run` kills only the process it started. On Windows the grandchildren (the Bash tool's shells, pytest) can keep running and hold files in the sandbox, so `runs.remove_tree(agent_box)` in the `finally` at `scripts/evals/produced_tests_mode.py`:90 (`remove_tree`, `scripts/evals/produced_tests_runs.py`:132-140) may fail. |
| Only the tail of the partial stdout is kept | :108-109 | The timeout message keeps `partial[-300:]`; the rest of the partial transcript is discarded. |

## Symptom

A live test-runner or test-writer eval row on the database-setting set fails an assertion although
the agent did the right thing (for example it piped a SQL file into `psql`, ran `pytest -k
"host=..."`, cited `README.rst:10`, or wrote "Tests OK"), or passes although it did not (for
example it overwrote the resolved DSN with a literal before connecting, or set `$env:PGHOST` in
PowerShell). Recorded gold rows are not affected.

## Detection

Read the failing assertion's `detail` in the results file. A `commands_no_db_address` detail
quoting a heredoc, a redirect or a non-Postgres program, a `report_names_no_address` detail quoting
a file reference, a version string or "localhost" inside a negation, or a not-run / outcome detail
on a report that plainly says the tests did not run (or ran), is this issue. A live run that ends
with a `remove_tree` error after "agent CLI timed out" is the timeout part.

## Workaround

Re-read a failing live row by hand before acting on its score. After a timeout on Windows, end the
left-over `bash` / `pytest` processes and delete the sandbox by hand.

## Suggested fix

Directions only; nothing here is applied.

- **Commands:** split each command (`simple_commands`) before applying `LIBPQ_RE`, and apply it
  only to Postgres clients, inline assignments and `python -c` driver code; skip heredoc and
  redirect tokens (anything starting with `<` or `>`) in `_positional_database`; also match
  PowerShell `$env:NAME=` assignments in `ENV_ADDRESS_RE`.
- **Reports:** extend `FILE_SUFFIXES` (`.rst`, `.ini`, `.sh`, `.cfg`-style config files, and so
  on) and require a digit-only host to be a full IPv4 address with a port or a DSN context; read
  `localhost` and the other address forms per clause, honouring negation; add the wording variants
  (`not attempted`, "Tests OK" as an outcome, the "passed? No" question shape, a skip that names
  a connection pool rather than the setting).
- **Produced tests:** make the taint flow-sensitive per function (a reassignment from an untainted
  value clears the name); anchor `ENV_KEY_RE` (for example `^(?:PG\w*|\w*DATABASE_URL|\w*DSN|DB_(?:URL|HOST|PORT|NAME|DSN))$`);
  ignore string constants used only in an `assert`; add `ConnectionPool`, `create_pool` and other
  pool constructors to `CONNECT_NAMES`.
- **Checker detection:** accept `python -m db_check.checker` and `-t <dir>`; exclude other non-run
  flags as well as `--help`.
- **Timeout:** start `claude` in its own process group (`start_new_session=True` on POSIX,
  `CREATE_NEW_PROCESS_GROUP` plus a tree kill such as `taskkill /T /F` on Windows) and kill the
  whole group on timeout; keep the full partial transcript (written next to the results) rather
  than only its last 300 characters.

**Related.** `KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows` is another Windows
live-path defect of the same eval harness.

**Pattern:** text checks that read a whole line, or a whole file, where the meaning depends on
which command, clause or point in the code the match sits in.
