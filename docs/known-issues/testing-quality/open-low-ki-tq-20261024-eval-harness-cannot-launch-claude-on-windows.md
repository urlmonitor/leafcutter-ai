---
title: "KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows — the eval harness starts the bare name 'claude' without a shell, which cannot launch the npm-installed claude.cmd on Windows, so every live row fails and the eval scores 0%"
description: "medium — scripts/evals/run_agent_eval.py runs ['claude', ...] through subprocess.run without a shell in invoke_via_cli and invoke_agent_writer. On Windows the npm install provides claude.cmd (and an extensionless shell script), which CreateProcess does not launch from a bare name, so each row raises 'claude CLI could not be launched' (or 'agent CLI could not be launched'), is recorded as a failed row, and the eval reports 0%. All four live evals run on 2026-10-24 scored 0% until PATH was prefixed with the folder of the npm package's native claude.exe."
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
  - docs/known-issues/testing-quality/open-high-ki-tq-20260908-0900.md
---

# KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows — bare 'claude' does not start on Windows

> Filed 2026-10-24. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. No live agent eval can run on a Windows machine with the standard npm
  install, and the failure is reported as a 0% quality score, not as a harness failure. CI
  (Linux) is not affected.
- **Status:** open, no AC.
- **Occurrences:** 4 on 2026-10-24: every live eval run that day (flow-author, mock-data-author,
  pt-classifier, restructuring-specialist) scored 0% with every row "claude CLI could not be
  launched" / "agent CLI could not be launched", until `PATH` was prefixed with the `bin` folder
  holding the npm package's native `claude.exe`.
- **First seen:** 2026-10-24 · **Last seen:** 2026-10-24
- **Where** (line numbers at `origin/main` `849791105`):
  - `scripts/evals/run_agent_eval.py`:259-301, `invoke_via_cli` (label evals). The argv starts with
    the bare name `"claude"` (:271-272) and goes to `subprocess.run` without `shell=True` (:286-292).
    An `OSError` becomes `ModelInvocationError("claude CLI could not be launched")` (:297-300).
  - `scripts/evals/run_agent_eval.py`:736-786, `invoke_agent_writer` (artifact evals). Same bare
    `"claude"` (:752-753), same `subprocess.run` (:769-777), `"agent CLI could not be launched"`
    (:782-785).
  - `scripts/evals/run_agent_eval.py`:1328-1339. A label row whose call fails is recorded with an
    empty prediction and a failed score, and the loop moves on to the next row.
  - `scripts/evals/run_agent_eval.py`:1125-1128. An artifact row whose call fails is recorded as
    `passed: false` with the error, and the loop moves on.

## Symptom

A live eval run on Windows prints a warning per row with "claude CLI could not be launched" (or
"agent CLI could not be launched"), then reports accuracy 0.0 and fails its threshold. `claude`
works from the same terminal, because the shell resolves `claude.cmd` through `PATHEXT`.

## Mechanism

1. **The npm install on Windows puts `claude`, `claude.cmd` and `claude.ps1` on `PATH`.** The
   extensionless `claude` is a POSIX shell script; `claude.cmd` is the batch wrapper the Windows
   shells use.
2. **`subprocess.run(["claude", ...])` without a shell goes to `CreateProcess`,** which appends only
   `.exe` to a bare name. It does not find or start a `.cmd` file, so the call raises
   `FileNotFoundError`.
3. **The harness treats that as a wrong answer per row.** The catch at :297-300 turns it into a
   `ModelInvocationError`, and the row loops record it as a failed row. Every row fails the same
   way, and the run reports 0% instead of stopping with "the CLI cannot be started".

## Detection

On Windows, run `python -c "import subprocess; subprocess.run(['claude', '--version'])"`. A
`FileNotFoundError` while `claude --version` works in the shell means the harness will hit this.
In a results file, every row carrying the "could not be launched" error is this issue.

## Workaround

Prefix `PATH` with the folder that holds the native `claude.exe` from the npm package
(under the global `node_modules` of `@anthropic-ai/claude-code`) before running the eval.

## Suggested fix

Directions only; nothing here is applied.

- **Resolve the executable first.** Use `shutil.which("claude")`, which honours `PATHEXT` and finds
  `claude.cmd`. Run a resolved `.cmd`/`.bat` through the shell (`cmd /c`) and anything else
  directly, or prefer a native `claude.exe` when one is found.
- **Allow an override.** Read the CLI path from an environment variable or the eval config, so a
  machine with an unusual install can point at it.
- **Fail fast.** When the CLI cannot be started, stop the run with one clear message before any
  row is scored, instead of recording every row as a failed answer.

**Related.** `KI-TQ-20260908-0900` is the same "could not be launched reads as a quality score"
problem seen from the scoring side; this entry is one concrete cause of it on Windows.

**Pattern:** a bare program name handed to a no-shell process call, on a platform where the
installed launcher is a script.
