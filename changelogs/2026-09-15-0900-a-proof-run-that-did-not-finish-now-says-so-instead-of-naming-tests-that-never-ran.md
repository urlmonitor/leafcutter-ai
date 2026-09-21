---
title: "A proof run that did not finish now says so, instead of naming tests that never ran"
date: "2026-09-15"
time: "09:00"
type: manual
components: 
  - build_orchestration
summary: "When the tool that certifies a requirement is done has its test run cut short by a timeout or a machine running out of resources, it now reports that the run did not finish instead of confidently naming specific tests as failed when they never actually ran."
description: "_run_pytest_and_parse previously recognised only TimeoutExpired as non-completion; a process killed outright by the OS (OOM, scheduler contention) returns a normal CompletedProcess with partial stdout and raises nothing, so it was missed and every unreported linked test was treated by _partition_linked_tests as failing. The fix keys on proc.returncode: pytest returns only 0 or 1 when a run reaches its conclusion, so any other code is treated as an incomplete run under the renamed _PYTEST_RUN_INCOMPLETE_SENTINEL, logged at WARNING, with no partial results exposed downstream. A control test confirms a completed run still names its real failures, so the fix cannot pass by suppressing failure reporting."
commits: 
  - 1d332c01
breaking: false
---

## Entry

### A confident, specific, wrong answer

The tool that decides whether a requirement is proven done runs its tests in a separate
process and reads the results back. When that process was cut short — a timeout, or the
machine killing it under load — the tool parsed whatever partial output it had received
and reported every test that had not yet reported as though the test itself had failed.
It named them by name.

That is worse than a blank or an error. A reader chasing a named test failure investigates
the test. The test was fine; the run simply never reached it. Real time was lost on this
branch's own predecessor tracking down failures that were never failures.

### Only one cause was recognised, and it was the rare one

The existing handling covered a genuine `subprocess` timeout — one cause, and the only
tunable one. A process killed outright by the operating system (out of memory, scheduler
contention, anything else that ends a process without it raising) returns a normal
completed process with partial stdout and no exception at all. That case was invisible to
the code, so it fell straight through into "these tests failed."

Both were observed on the same underlying ticket: a genuine budget overrun on one run, and
a kill under a large override on another where the machine was simply busy.

### The fix keys on completion, not on cause

Rather than try to enumerate every way a test process can die — the causes are open-ended
and most are not tunable — the fix checks whether the run reached a conclusion at all.
Pytest returns exactly two codes when it runs every collected test to completion: `0` (all
passed) and `1` (some failed). Any other code means the run did not finish, and is now
reported that way: logged at WARNING, with no partial results exposed downstream, and the
operator-facing reason renamed from a timeout-specific sentinel to one that just means "the
run did not finish."

### Behaviour on a completed run is unchanged

A run that actually finishes still names its real failures — that has not changed. A
dedicated control test asserts exactly that, so the fix cannot have earned its result by
going quiet on genuine failures; it only changes what happens when the run never reported
at all.
