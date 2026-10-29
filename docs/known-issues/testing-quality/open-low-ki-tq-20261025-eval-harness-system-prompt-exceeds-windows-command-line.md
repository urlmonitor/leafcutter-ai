---
title: "KI-TQ-20261025-eval-harness-system-prompt-exceeds-windows-command-line — the eval harness passes the agent template as a command-line argument, and the test-writer template is over twice Windows' 32,767-character limit, so every test-writer live row fails at launch"
description: "medium — scripts/evals/run_agent_eval.py invoke_agent_writer puts the rendered agent template on the claude command line as the --append-system-prompt value (invoke_via_cli does the same with --system-prompt, and produced_tests_transcript.invoke_with_transcript with --append-system-prompt). The test-writer template renders to about 67,700 characters (about 67,900 on the quoted command line), over the 32,767-character limit of a Windows command line, so CreateProcess raises FileNotFoundError [WinError 206] ('file name or extension is too long') and every test-writer live row is recorded as 'agent CLI could not be launched'. The live before-score of 2026-10-25 scored test-writer 0/8 for this reason; the test-runner, sql-test-writer and test-designer templates (10,100 to 18,500 characters) launched. Linux is not affected at this size."
type: reference
category: reference
status: active
created: '2026-10-25'
last_updated: '2026-10-25'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/known-issues/testing-quality/open-low-ki-tq-20261024-eval-harness-cannot-launch-claude-on-windows.md
  - docs/known-issues/testing-quality/open-high-ki-tq-20260908-0900.md
---

# KI-TQ-20261025-eval-harness-system-prompt-exceeds-windows-command-line — the test-writer template is too long for a Windows command line

> Filed 2026-10-25. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. The test-writer live eval cannot be taken on Windows at all, and the
  failure is reported as a 0% score, not as a harness failure. Recorded gold scoring
  (`--score-gold`) makes no model call and is unaffected; Linux CI is not affected at this size.
- **Status:** open, no AC.
- **Occurrences:** 1 (the live before-score on 2026-10-25, Windows 11, `run_agent_eval.py
  --agent test-writer` without `--score-gold`, results timestamp `2026-10-25T21:10:20Z`): all 8
  rows failed with `ModelInvocationError('agent CLI could not be launched')`, each logged with
  `FileNotFoundError: [WinError 206] Der Dateiname oder die Erweiterung ist zu lang` ("the file
  name or extension is too long") from `invoke_agent_writer`.
- **First seen:** 2026-10-25 · **Last seen:** 2026-10-25
- **Where** (line numbers at `origin/main` `5e5a37380`):
  - `scripts/evals/run_agent_eval.py`:684-733, `invoke_agent_writer`. The argv (:700-713) carries
    the whole template as the value of `"--append-system-prompt"` (:706-707) and goes to
    `subprocess.run` (:717-725). The `OSError` becomes the constant
    `"agent CLI could not be launched"` (:730-733), so the WinError 206 detail survives only in the
    logged traceback, not in the results file.
  - `scripts/evals/produced_tests_mode.py`:97-103. The produced-tests live path renders the
    template (`render_prompt` :41-43, which only substitutes `{{config.output_root}}`) and passes it
    to `invoke_agent_writer` (:103) — or, for an agent with `capture_transcript` (test-runner,
    `scripts/evals/agent_eval_config.json`:167), to
    `scripts/evals/produced_tests_transcript.py`:98-116, `invoke_with_transcript`, whose argv
    (:101) also carries the template as the `"--append-system-prompt"` value. Same exposure, same
    `"agent CLI could not be launched: ..."` record (:112-115).
  - `scripts/evals/run_agent_eval.py`:259-300, `invoke_via_cli` (label evals). Same construction
    with `"--system-prompt"` (:277-278). No label template is near the limit today.
  - `scripts/evals/run_agent_eval.py`:234-242, `load_system_prompt`: the system prompt is the
    template body below its frontmatter, with nothing trimmed.

### Template sizes

Measured at `5e5a37380` with `load_system_prompt` and `render_prompt` over a typical Windows
sandbox path; "command line" is `subprocess.list2cmdline` of `claude -p x --append-system-prompt
<prompt>`, which adds a backslash before every `"` in the template.

| Agent | Template body | Rendered | Command line (quoted) | Launches on Windows |
|---|---|---|---|---|
| test-writer | 67,445 | 67,718 (7 placeholders) | 67,913 | no — over 32,767 |
| test-designer | 18,434 | 18,434 | 18,499 | yes |
| sql-test-writer | 16,232 | 16,388 (4 placeholders) | 16,531 | yes |
| test-runner | 10,014 | 10,092 (2 placeholders) | 10,159 | yes |
| flow-author (artifact) | 10,181 | — | — | yes |
| mock-data-author (artifact) | 7,933 | — | — | yes |
| pt-classifier (label) | 6,441 | — | — | yes |
| restructuring-specialist (label) | 5,989 | — | — | yes |

The row's user input is a further argv value on top of these.

## Symptom

`python scripts/evals/run_agent_eval.py --agent test-writer` on Windows logs one
`agent CLI could not be launched` traceback per row ending in `FileNotFoundError: [WinError 206]`,
prints `row <id> could not be scored: ModelInvocationError('agent CLI could not be launched')`,
and reports accuracy 0.0 with empty `per_assertion`. The other three local-only agents
(test-runner, sql-test-writer, test-designer) launch and score normally on the same machine and
the same `PATH`.

## Mechanism

1. **The harness hands the system prompt to `claude` as an argv value.** Every invoker builds a
   list whose `--system-prompt` / `--append-system-prompt` value is the whole rendered template.
2. **Windows joins argv into one command-line string for `CreateProcess`,** and that string may
   be at most 32,767 characters. The test-writer template alone is about 67,900 characters once
   quoted.
3. **`CreateProcess` fails with error 206, which Python raises as `FileNotFoundError`.** It looks
   like a missing program, but `claude.exe` was found (a missing program is WinError 2, see
   `KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows`).
4. **The row loop records it as a failed answer.** Every row fails identically, and the run
   reports 0% instead of stopping with "the CLI cannot be started".

## Detection

In the run's log, `[WinError 206]` under an `agent CLI could not be launched` or
`claude CLI could not be launched` traceback is this issue. In the results file alone it reads
exactly like the bare-name launch failure; check the log. To check a template before a run:
`len(load_system_prompt(Path("templates/agents/<agent>.md")))` near or over 32,000 will fail on
Windows.

## Workaround

None inside the harness. Take the test-writer live before-score on Linux (or WSL), or
temporarily change the invoker to pass the prompt through a file (below) in a scratch copy.

## Suggested fix

Directions only; nothing here is applied.

- **Pass the prompt through a file, not argv.** Write the rendered prompt to a temp file and pass
  `--append-system-prompt-file <path>` (and `--system-prompt-file <path>` in `invoke_via_cli`).
  The installed CLI (2.1.205, `claude.exe` under the npm `@anthropic-ai/claude-code/bin`) does
  not list either flag on its own in `claude --help`, but its `--bare` entry names
  `--system-prompt[-file]` and `--append-system-prompt[-file]` as the ways to supply context, so
  the file variants exist; confirm with one call before relying on them. The user input can go
  on stdin with `-p` and no positional prompt, which removes the second large argv value.
- **Fix all three invokers together.** `invoke_agent_writer`, `invoke_with_transcript` and
  `invoke_via_cli` build the command the same way; a shared builder would keep them in step.
- **Keep the cause in the record.** Put `repr(exc)` into the `agent CLI could not be launched`
  message, as `invoke_with_transcript` already does, so the results file shows WinError 206.
- **Fail fast.** When the CLI cannot be started, stop before scoring any row (the same direction
  as the related entries below).

**Related.** `KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows` is the other Windows
launch failure of the same invokers: the bare name `claude` cannot start `claude.cmd`
(WinError 2). Its workaround (prefix `PATH` with the folder of the native `claude.exe`) was in
place for this run, which is why the failure here is 206, not 2; fixing one does not fix the
other. `KI-TQ-20260908-0900` is the scoring-side problem both feed: "could not be launched" is
reported as a quality score.

**Pattern:** a large payload passed as a command-line argument, which works until the payload
outgrows the smallest command-line limit of a supported platform.
