# Agent evaluation scripts

`run_agent_eval.py` runs the configured classifier and artifact evaluations. Gold
rows and pass thresholds live in `agent_eval_config.json` and its referenced sets.

Artifact evaluations use a temporary copy of the configured Product Truth store.
`artifact_dependencies.py` adds only declared schemas, example receipts, planning
sources and referenced ACs, plus the reviewed model resolver's local Python import
closure. It preserves the existing capability marker, rejects linked or escaping
paths, and excludes environment files and caches. It does not call providers.
`artifact_validation.py` checks canonical validator completion and target reports;
`label_scoring.py` contains the classifier's pure scoring calculations.
`cli_envelope.py` reads the `claude` CLI's JSON envelope. When the CLI exits
non-zero with empty stderr, as it does with no credential, the row error carries
the envelope's `result` text, for example `Not logged in · Please run /login`.

Store validation compares new errors with the baseline. The produced flow's
contracts also require an independent successful check, so an unavailable model
or receipt cannot be hidden by an identical baseline error. A crashed validator
is a harness error. A failure to start the agent CLI stops the run as a harness failure
(see "Exit statuses"), but a failure after the agent started, such as a timeout, a
non-zero exit or a malformed reply, stays in the accuracy denominator without becoming a
fabricated negative prediction.

Offline verification: `python -m unittest unit_tests.product_truth.test_flow_io_contract_eval`.
Self-test and gold-score modes prove harness behavior, not model quality; they
must not replace live evaluation receipts or their freshness stamps.

## How a live run starts the agent

A live run starts the `claude` CLI once per row, in `agent_launch/command.py`. The
instructions travel in a prompt file and the row input travels on stdin, so no
command line holds either of them. That matters on Windows, where a command line
has a limit of 32,767 characters, and the test-writer template alone renders to about
67,700 characters.

| Scoring mode | Instruction flag | Effect |
|---|---|---|
| `label` | `--system-prompt-file` | The instructions replace the default instructions. |
| `artifact`, `produced_tests`, recorded commands (`capture_transcript`) | `--append-system-prompt-file` | The instructions are added to the default instructions. |

- **The prompt file** holds the rendered instructions as UTF-8 with no newline
  translation. It is written to the OS temp directory, never to the row sandbox or the
  project tree, and it is removed after the row whether the agent succeeded, exited
  non-zero, timed out or failed to start.
- **The input** goes on stdin as the UTF-8 bytes of the row input; `-p` has no prompt
  text after it. The command line holds only the model, the tool list, the output
  format, the prompt-file flag and the path of the prompt file.
- **Confirmed on claude CLI 2.1.205** (Windows 11): both prompt-file flags are
  accepted, and `-p` with no positional prompt reads its input from stdin.

Steps, commands and troubleshooting are in
[Run a live agent eval](../../docs/how-to/run-a-live-agent-eval.md).

## How the harness finds claude

`agent_launch/locate.py` answers with the first of these:

1. The setting `LEAFCUTTER_EVAL_CLAUDE_CLI`, the path of the program to start, on every
   platform. A value that names no program is a launch failure; the harness does not
   fall back to the path.
2. On Windows, the lookup the Windows command shell does: the `PATH` folders in order
   and the extensions in `PATHEXT` (`shutil.which`).
3. Elsewhere, the program named `claude` on `PATH`.

A `.cmd` or `.bat` launcher, which is what the standard npm install provides on Windows,
cannot be started directly. The harness starts it through the command processor
(`cmd /d /s /c "..."`), with the path of the prompt file always in double quotes. A
`.exe` and every program on Linux are started directly, from a list, with no shell.

Use the setting when the install is unusual or when several installs exist, for example
in PowerShell:

```powershell
$env:LEAFCUTTER_EVAL_CLAUDE_CLI = "C:\Users\me\AppData\Roaming\npm\claude.cmd"
```

or in a POSIX shell:

```bash
export LEAFCUTTER_EVAL_CLAUDE_CLI=/usr/local/bin/claude
```

## When the agent cannot be started

A run whose agent could not be started stops, and the text is in `harness_failure.detail` of the results file (no row carries it):

```text
agent CLI could not be launched: <ExceptionType>: <message>
```

The operating-system error is kept exactly as raised, so the results file alone tells
the causes apart. For example, `OSError: [WinError 206] The filename or extension is
too long` means a command line over the limit (the harness should never build one;
report it), and `FileNotFoundError: [WinError 2] The system cannot find the file
specified` means no program was found (see "How the harness finds claude"). On Linux a
refusal reads `PermissionError: [Errno 13] Permission denied: '<path>'`. The text is the
same for label, artifact, produced-tests and recorded-commands runs. A failure after the
agent started (a timeout, a non-zero exit, a reply that cannot be read) keeps its own
text and is not a launch failure.

The run does not go on to the next row. It stops as a harness failure: it prints one
line naming the failure, writes a results file with a top-level `harness_failure` object
(`cause`, `row`, `detail`) and no accuracy, pass rate, per-assertion or score keys, and
ends with exit status 3. `eval_selector.py --check` treats that file as no result, never
as a fresh receipt.

## Exit statuses

`run_agent_eval.py` ends with one of four statuses:

- `0`: the run scored every row and met the threshold.
- `1`: the run scored every row and fell below the threshold.
- `2`: usage or configuration error; nothing was scored.
- `3`: harness failure: the agent CLI could not be started; no row was scored beyond the
  first and the results file carries `harness_failure`, not a score.

## The CI gate is informational

`.github/workflows/agent-evals.yml` (`Agent evals (affected)`) is **not** a
required check. This was the owner's decision on 2026-10-06
(`TICKET-20261006-AgentEvalGateHonestAboutCredentials`).

- **No credential.** The repository has no `ANTHROPIC_API_KEY` secret. When a PR
  affects an agent, the `Preflight — model credentials` step fails before any row
  runs, with an explicit "no model credentials" error and no score. A red check
  from that step means nothing was evaluated. It does not mean an agent regressed.
- **Triggers.** Each agent's `triggers` list in `agent_eval_config.json` names only
  that agent's own files:
  - its template, its own schema and its eval set;
  - the product-truth store paths it reads;
  - the store entry scripts the harness runs;
  - the shared harness.

  The list leaves out the sandbox's transitive contract dependencies, such as
  kernel, knowledge or integrations code, `config/`, `reports/`, `docs/analysis/`
  and AC YAML. So a PR that only touches those affects no agent.
- **Making it blocking.** This needs two repository-settings changes: add the
  secret, then add the check to the main ruleset's required status checks.

## Produced-tests mode (local only)

`scoring_mode: "produced_tests"` scores an agent whose output is test files plus a
completion report. It is implemented in `produced_tests_mode.py` (row loop, report,
payload), `produced_tests_scoring.py` (assertion kinds) and `produced_tests_runs.py`
(the git sandbox, pytest runs and the wrong-version run). The test-writer set,
`sets/test-writer.jsonl`, is its first user.

- **Rows.** `expected` carries `negative`, `fixture` (a project directory), `gold_output`
  (a recorded output directory) and `assertions` (`{"kind": ...}`). Each row runs in a
  fresh temp git repository: the fixture is the base commit. Recorded tests are stored as
  `*.py.recorded` so a bare `pytest` never collects them. Fixture projects live under
  `sets/test-writer/projects/`, recorded outputs under `sets/test-writer/recorded/`, and
  only the placeholder database address is used.
- **Scoring is deterministic.** Every assertion kind reads the output and calls no model;
  each kind is described, with its rules and examples, in the
  [assertion-kinds reference](../../docs/reference/produced-tests-eval-assertion-kinds.md).
  The refresh-gate row's test half is a real run of the shared
  wrong-version runner (`halves.test` carries the runner's verdict, `halves.report` the
  report check). A judge, if a row has a rubric, is secondary and never decides a test half.
- **Rules.** A to-run-later entry counts when its test id names the function and its wrong version is non-empty ([`sql_to_run_later_names_wrong_version`](../../docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md#sql_to_run_later_names_wrong_version)).
- **Counts.** The exact processed-row count and the non-NULL count may be computed in SQL or asserted on the fetched rows; a `>= 0` or "at least one row" assertion is not a count ([`sql_counts_rows_and_non_null`](../../docs/reference/produced-tests-eval-assertion-kinds-sql-test-writer.md#sql_counts_rows_and_non_null)).
- **Address.** A report names an address only when a scheme is followed by a host, so relaying the checker's own message passes ([`report_names_no_address`](../../docs/reference/produced-tests-eval-assertion-kinds-database-setting.md#report_names_no_address)).
- **PASS.** A test-runner report may claim a pass (`PASS` in upper case, or a Status / Result of pass in any case) only when it quotes a passed-test count above zero from the runner's summary ([`report_pass_quotes_a_count`](../../docs/reference/produced-tests-eval-assertion-kinds-database-setting.md#report_pass_quotes_a_count)); the test-runner set has four rows: `configured-database`, `missing-setting-database-work`, `missing-setting-no-database-work` and `no-test-collected`.
- **Not run.** The test-runner's "Database Not Configured" block ends with the sentence "The database tests were not run.", so a report that relays it says the tests were not run ([`report_says_not_run`](../../docs/reference/produced-tests-eval-assertion-kinds-database-setting.md#report_says_not_run)).
- **Offline.** `python scripts/evals/run_agent_eval.py --agent test-writer --score-gold`
  replays the recorded gold outputs, scores every row and calls no model.
- **Local only.** `agents["test-writer"].local_only` is true: `eval_selector.py` keeps
  it out of `affected` and out of `--check`, so the CI job neither runs it nor demands a
  fresh result. Every payload carries `run_context: "local"` and the printed report says
  "LOCAL RUN". A live run (`--agent test-writer` without `--score-gold`) needs model
  credentials and is never run in CI.
- **Keeping a live run's outputs.** A live row's output lives in a temporary folder that
  is deleted after scoring. To check a failed row against what the agent really wrote, set
  `LEAFCUTTER_EVAL_KEEP_OUTPUTS` to a directory before the run. Each live row's output
  (`files/` with every file the agent changed, `report.md`, the to-run-later `leafcutter/`
  folder and, when captured, the transcript) is then copied to
  `<dir>/<set name>/<row id>/`, for passing and failing rows alike. A re-run replaces a
  row's folder. Unset, or with `--score-gold`, nothing is kept.
