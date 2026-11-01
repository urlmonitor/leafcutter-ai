---
title: "KI-TQ-20261101-eval-launcher-review-lows — low-severity gaps in the eval agent launcher found by the TQ-200d-5 reviews and left unfixed"
description: "low — scripts/evals/agent_launch/ (TQ-200d-5): the timeout watchdog starts before the process and allows 0.5 s, psutil is only a dev dependency, the outer except OSError still labels some post-start errors as launch failures, a direct Linux exec leaves grandchildren alive after a timeout, and four edge cases of the Windows .cmd route (%VAR% in TEMP, a missing .cmd target, lone surrogates, an unverified Linux stdin route). None was observed in a run."
type: reference
category: reference
status: active
created: '2026-11-01'
last_updated: '2026-11-01'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/how-to/run-a-live-agent-eval.md
  - docs/acceptance-criteria/testing-quality/TQ-200-per-agent-eval-coverage/TQ-200d-5.yaml
---

# KI-TQ-20261101-eval-launcher-review-lows — gaps left in the eval agent launcher

> Filed 2026-11-01. Index: [testing-quality.md](../testing-quality.md). Filename severity is the
> three-level index bucket (`low`); the original grading is the `**Severity:**` line below.

- **Severity:** low. Each item is a narrow edge case; none was seen in a run, and every one fails
  visibly (a wrong error class or a slow timeout), not with a false score.
- **Status:** open, no AC. Found by the pr-reviewer rounds of TQ-200d-5 (2026-11-01); the
  high-confidence findings were fixed in that work, these lows were not.
- **Occurrences:** 0 observed runs; found by code review.
- **First seen:** 2026-11-01 · **Last seen:** 2026-11-01
- **Where:** `scripts/evals/agent_launch/command.py` (`launch`, `kill_launcher_tree`, `_staged`),
  `scripts/evals/agent_launch/locate.py`, `requirements-dev.txt`.

## Symptom

None observed. Each item below names the input that would show it.

## Mechanism and items

1. **The watchdog can fire before the run's own timeout.** The `threading.Timer(timeout + 0.5)` is
   started before `subprocess.run` creates the process, while `run`'s clock starts after creation.
   If creating the process takes more than 0.5 s (a slow antivirus scan on Windows), the watchdog
   kills the tree first and the caller sees a non-zero exit instead of `TimeoutExpired`, so a row
   gets a post-start error where a timeout was due.
2. **Without psutil the Windows timeout hangs again.** psutil is declared only in
   `requirements-dev.txt`. When it cannot be imported, `kill_launcher_tree` logs a warning and
   returns, and a timeout on the `.cmd` route waits for the agent to exit, which is the defect
   TQ-200d-5's review round 1 fixed.
3. **The outer `except OSError` is still wide.** An `OSError` raised after the process started (a
   pipe read error) or by `mkstemp` is reported as "agent CLI could not be launched" and stops the
   run, although only a refused start is a launch failure by TQ-200d-5-i.
4. **A direct Linux exec leaves grandchildren alive.** On Linux the CLI is the started process; when
   it is killed on a timeout its own children are reparented and their command lines do not hold the
   prompt-file path, so the watchdog does not find them.
5. **Windows `.cmd` route edge cases** (review round 1, not fixed): a `%VAR%` sequence in the TEMP
   path is expanded by `cmd.exe`; a `.cmd` whose target program is missing reports `cmd.exe`'s
   message rather than an OS error; a lone surrogate in the instructions fails the UTF-8 write; the
   Linux stdin route is covered by the Docker test run but not by a live run.
6. The watchdog and the exception handler can both run `kill_launcher_tree` (harmless), and
   `psutil.process_iter` over every process can take a second or more on a loaded machine.

## Fix direction

Start the watchdog after the process exists, or allow a margin of several seconds; make psutil a
runtime requirement of the eval harness, or fail loudly when it is missing on Windows; narrow the
outer handler to the start call; kill by process group on Linux.
