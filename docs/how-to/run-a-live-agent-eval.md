---
title: "How to run a live agent eval"
description: "Run an agent eval live on your machine with run_agent_eval.py: check the scorer offline, run a label, an artifact or a produced-tests agent, read the results file, and recover from a launch failure or a harness failure."
type: how-to
status: active
created: 2026-11-01
last_updated: 2026-11-01
components:
  - testing_quality
related_docs:
  - scripts/evals/README.md
  - docs/known-issues/testing-quality.md
  - docs/how-to/documentation/write-how-to.md
---

# How to run a live agent eval

A live run starts the real `claude` CLI for each row of an agent's eval set and scores what the agent answered or produced. Run one when you changed an agent's template and want a score from a model, not from the recorded gold output.

The instructions travel in a prompt file and the row input travels on stdin, so the length of a template is no longer a Windows limit. [`scripts/evals/README.md`](../../scripts/evals/README.md) explains the route.

## Prerequisites

- Model credentials for the `claude` CLI (`claude` runs from your terminal and answers).
- A working `claude` CLI that the harness can find; see "Finding claude on Windows" below.
- The repository's Python environment, with the commands run from the repository root.

## Steps

### Step 1 - Prove the scorer offline

Score the recorded gold outputs. This calls no model and should end near 100%:

```bash
python scripts/evals/run_agent_eval.py --agent test-writer --score-gold
```

### Step 2 - Run a produced-tests agent live

The four produced-tests agents are local only. Each run prints `LOCAL RUN` and writes `run_context: "local"`; the CI eval gate never runs them. Run one agent at a time:

```bash
python scripts/evals/run_agent_eval.py --agent test-writer
python scripts/evals/run_agent_eval.py --agent sql-test-writer
python scripts/evals/run_agent_eval.py --agent test-designer
python scripts/evals/run_agent_eval.py --agent test-runner
```

To try one row first, add `--row` with the row id, for example `python scripts/evals/run_agent_eval.py --agent test-runner --row configured-database`.

### Step 3 - Run a label agent live

A label agent answers with booleans that are compared with the row's expected labels:

```bash
python scripts/evals/run_agent_eval.py --agent pt-classifier --limit 3
```

### Step 4 - Run an artifact agent live

An artifact agent writes files in a throwaway sandbox copy, and the files are scored:

```bash
python scripts/evals/run_agent_eval.py --agent mock-data-author --limit 2
```

### Step 5 - Read the results file

Each run writes `scripts/evals/results/<agent>.json`; add `--results-file <path>` to write it elsewhere. Open it and read:

- `aggregate`: the accuracy and the tallies.
- `rows`: one entry per row. Each has `score.passed`, the per-assertion detail in `score.assertions` (label rows: `score.per_axis`), and `error` (label rows: `parse_error`) when the row failed after the agent started.

## Verification

The run ends with a `GATE:` line and exit status `0` (met the threshold) or `1` (below it). A produced-tests run also prints `LOCAL RUN`, and the results file holds `aggregate` and `rows`. Exit status `3` means the run stopped as a harness failure; see below.

## Troubleshooting

### Reading a launch failure

A run whose agent could not be started stops at that row, and the text is in `harness_failure.detail` of the results file (never in a row's `error`):

```text
agent CLI could not be launched: <ExceptionType>: <message>
```

The operating-system error is kept as raised, so the results file alone tells the causes apart:

| Text | Meaning | What to do |
|---|---|---|
| `[WinError 206]` (the file name or extension is too long) | Windows refused a command line over 32,767 characters. | Report it. The harness keeps the instructions in a file and the input on stdin, so it should never build such a command line. |
| `[WinError 2]` (the system cannot find the file specified) | No program named `claude` was found, or the setting names a missing file. | See "Finding claude on Windows". |
| `[Errno 13] Permission denied` (Linux) | The program exists and cannot be run. | Fix the file's permissions. |

A timeout, a non-zero exit or a reply that cannot be read is not a launch failure: the agent started, the row counts as failed, and the run goes on.

### Finding claude on Windows

The harness looks for the program the way the Windows command shell does: the `PATH` folders in order, with the extensions in `PATHEXT`. The standard npm install provides `claude.cmd` (and `claude.ps1`), and the harness starts a `.cmd` launcher through the command processor, so nothing needs to be changed for it.

To start a different program, set `LEAFCUTTER_EVAL_CLAUDE_CLI` to its path. The setting wins on every platform and the path is not searched when it names a missing program:

```powershell
$env:LEAFCUTTER_EVAL_CLAUDE_CLI = "C:\Users\me\AppData\Roaming\npm\claude.cmd"
```

To see what the shell finds, run `where claude` in `cmd`; the first `.exe`, `.cmd` or `.bat` listed is the one the harness starts.

### A run that stops as a harness failure

When the agent cannot be started at all, scoring more rows would only repeat the failure. The run stops at the first row and:

- prints one line that starts with `HARNESS FAILURE`, naming the row and the launch-failure text;
- ends with exit status 3, different from the exit status 1 of a run that scored below its threshold;
- writes the results file with a `harness_failure` object (`cause`, `row`, `detail`) and no score: there is no accuracy, no pass rate and no `rows`, so nothing in it reads as 0%.

The file is never a fresh eval receipt for `eval_selector.py --check`. Read the `detail` as described in "Reading a launch failure", fix the launch, and run the eval again.

## See Also

- [`scripts/evals/README.md`](../../scripts/evals/README.md): the launch route, the exit statuses and the results-file keys.
- [Known issues: testing quality](../known-issues/testing-quality.md): the recorded Windows launch defects and their resolution.
