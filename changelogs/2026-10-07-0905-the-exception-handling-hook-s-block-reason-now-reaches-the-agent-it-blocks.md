---
title: "The exception-handling hook's block reason now reaches the agent it blocks"
date: "2026-10-07"
time: "09:05"
type: manual
components: 
  - commit_guardian
summary: "Fixed a guard that blocks risky exception-handling edits so the person being blocked can now see why, instead of the edit landing anyway with no stated reason."
description: "One commit (04ba2e33) to templates/hooks/check_exception_handling_hook.py: both sys.exit(2) blocking branches (ruff-not-found and ruff-violations-found) wrote their explanation with a bare print() to stdout, but Claude Code only reads PostToolUse blocking feedback from stderr, so the reason was silently discarded while the edit still succeeded; both now use file=sys.stderr, matching the OSError fail-open branch already in the same function, and the module docstring's hook-contract line is corrected to match. Also narrows three pre-existing blind except clauses in the same file (payload-parse, path-resolve, and subprocess.run in _run_ruff) to specific exception types per the Error Handling Policy, with no behavior change. Three new tests plus two corrected pre-existing tests that had asserted on stdout."
commits: 
  - 04ba2e33
---

## Entry
