---
title: "Live agent evals pass the agent's instructions as a file and start the CLI the same way on Windows and Linux; a run that cannot start the agent stops with the operating-system reason"
date: "2026-11-01"
time: "21:30"
type: manual
components:
  - testing_quality
summary: "scripts/evals/agent_launch/ starts the agent CLI for every eval invoker: the instructions go in a temp file named by --system-prompt-file / --append-system-prompt-file and the input on stdin, so no argument nears the Windows command-line limit; the CLI is found through LEAFCUTTER_EVAL_CLAUDE_CLI or the PATH (claude.cmd through cmd /d /s /c on Windows, the program itself on Linux). When the CLI cannot be started, the run stops with exit status 3 and writes a results file carrying a harness_failure marker with the exception class, number and message, never an accuracy or pass rate, and the eval selector does not accept that file as a receipt."
description: "TQ-200d-5, TQ-200d-5-i, TQ-200d-5-ii, TQ-200d-5-iii. The 2026-10-25 live before-score could not launch test-writer on Windows: its instructions inlined on the command line exceeded the 32,767-character limit (KI-TQ-20261025-eval-harness-system-prompt-exceeds-windows-command-line and KI-TQ-20261024-eval-harness-cannot-launch-claude-on-windows, both moved to resolved). New package scripts/evals/agent_launch/ (command.py launch(), locate.py find_claude(), harness_failure.py launch_failed/stop_run/receipt_shas); run_agent_eval.py, produced_tests_transcript.py, produced_tests_mode.py and eval_selector.py route through it. Review round 1 (test-first): a timeout or Ctrl-C on the .cmd route killed only cmd.exe and waited for the agent, so a psutil watchdog now kills the launcher's whole process tree; a failed temp-file cleanup is logged instead of becoming a launch failure; --score-gold and --self-test harness failures write the suffixed results file instead of overwriting the live receipt; the docs name harness_failure.detail. Round 2 re-review found no high-confidence issue; its lows are filed as KI-TQ-20261101-eval-launcher-review-lows. Docs: scripts/evals/README.md sections and the new docs/how-to/run-a-live-agent-eval.md. Tests unit_tests/evals/tq200d5/ (57 with the edited prompt-file test) pass on Windows and Linux (Docker) with none skipped. Wrong-version gate: 27 named versions, all caught."
commits:
breaking: false
---

## Entry

Live agent evals now start the agent on Windows as reliably as on Linux. The agent's instructions are
handed over in a file rather than on the command line, so long instructions no longer hit the Windows
length limit. If the agent cannot be started at all, the run stops at once and says why, instead of
scoring every row as a failure and reporting a misleading low score.
