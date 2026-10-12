---
title: "Kernel: the printed decisions-publish command runs as shown"
status: todo
components:
  - decision_kernel
created: 2026-10-02
depends_on: []
priority: medium
roadmap_phase: phase_kernel_1_founding
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - decision-kernel
last_updated: 2026-10-02
agents:
  test-writer: signed_off
  python-coder: signed_off
  pr-reviewer: signed_off
  commit: signed_off
  pull-request: needed
---

# Kernel: the printed decisions-publish command runs as shown

## Actor / Goal
In order that the owner can publish a staged decision record by copying the command the kernel prints, we need that command to work as printed.

## Context
- **Live reproduction (2026-10-02):** the staged-record limitation printed `publish it for review with: python -m kernel decisions publish --run-id run-49c4f5e97f2d41d6`. Run in the owner's PowerShell, it failed with `C:\Python314\python.exe: No module named kernel`: plain `python` is the system interpreter, without the project venv or the kernel's `PYTHONPATH`.
- The command also writes into the kernel checkout's `docs/decisions/`, which the message does not say.

## Scope (no acceptance criteria by user decision)
- The printed command names the interpreter the kernel itself runs under (`sys.executable`), and the module path or a documented wrapper, so it works copied verbatim from any shell. It also states the folder it writes to.
- Tests: the limitation text contains `sys.executable`, and the path needed to import `kernel`; a smoke test runs the printed command in a subprocess from an unrelated directory against a fixture run and gets a JSON result.

## Comments
### 2026-10-02 12:00 — test-writer (status: ok)
feedback-id: (submit-failed)
Wrote tests/kernel/memory/test_publish_command_runnable.py (4 tests, red). Printed command must be plain argv after "publish it for review with: " (no cd/&&/env prefix), contain sys.executable and repo_root(); text before it names the docs/decisions folder. Existing assertions on "python -m kernel decisions publish" in test_decision_precedent.py / test_learning_loop_e2e.py will need updating by python-coder.
red_baseline:
  - test_name: test_ac1_names_the_interpreter_the_kernel_runs_under
    file: tests/kernel/memory/test_publish_command_runnable.py
    error: "AssertionError: sys.executable not in printed command"
  - test_name: test_ac4_printed_command_runs_from_an_unrelated_directory
    file: tests/kernel/memory/test_publish_command_runnable.py
    error: "AssertionError: 'No module named' unexpectedly found in 'C:\Python314\python.exe: No module named kernel'"
completion_manifest:
  cross_layer_seam_answer:
    result: covered
    producing_side: "executor._stage limitation text from a real staged run"
    consuming_side: "subprocess execution of the printed command (kernel CLI)"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "printed command run via subprocess (python -m kernel decisions publish equivalent)"

## Implementation Tasks
### test-writer
- [x] Update stale assertion tests/kernel/memory/test_learning_loop_e2e.py:126 (expects "python -m kernel decisions publish --run-id R"); the printed command is now `<sys.executable> <repo_root>/run_kernel.py decisions publish --run-id R` (assert via kernel.capabilities.decision.publish_command.publish_command(run_id)).

### 2026-10-02 12:30 — python-coder (status: handoff)
feedback-id: (submit-failed)
Added kernel/capabilities/decision/publish_command.py (publish_command, publish_folder), repo-root launcher run_kernel.py (puts repo root on sys.path, no PYTHONPATH needed), and executor._stage now prints the folder and the runnable command. All 4 new tests green; test_decision_precedent green. test_learning_loop_e2e.py:126 asserts the old text and needs a test-writer update (I may not edit tests).
red_baseline_results:
  - test_name: test_ac1_names_the_interpreter_the_kernel_runs_under
    result: green
  - test_name: test_ac4_printed_command_runs_from_an_unrelated_directory
    result: green

### 2026-10-02 13:00 — test-writer (status: ok)
feedback-id: (submit-failed)
(classification: test_drift) test_learning_loop_e2e.py:126 asserted the old "python -m kernel" text; production is correct. Now asserts publish_command(run_id) is in the staged note. test_learning_loop_e2e + test_publish_command_runnable: 13 passed.

### 2026-10-02 13:30 — python-coder (status: ok)
feedback-id: (submit-failed)
Final pass: publish_command.py, run_kernel.py and executor._stage change complete; test_publish_command_runnable + test_learning_loop_e2e: 13 passed. Stale e2e assertion already fixed by test-writer (test_drift).
red_baseline_results:
  - test_name: test_ac1_names_the_interpreter_the_kernel_runs_under
    result: green
  - test_name: test_ac4_printed_command_runs_from_an_unrelated_directory
    result: green

### 2026-10-02 14:00 — pr-reviewer (status: ok)
feedback-id: (submit-failed)
Manual review of the small diff (no Agent Contracts; v1 fallback). No high-confidence findings. Old-text grep: no tests assert the old command; remaining docs mention the generic `python -m kernel decisions publish` form only.
[M-1] publish_command.py:_quote — on Windows a path with spaces is wrapped in double quotes; PowerShell needs a leading `& ` to run a quoted executable path, so the printed command may still fail there if sys.executable or the repo path contains spaces. Not blocking.
Suppressed: 1 low nit (executor.py import order: publish_command import precedes assess).
Escalation: not escalated, medium count 1.

### 2026-10-02 14:30 — commit (status: blocker)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "feat(kernel): make printed decisions-publish command runnable as shown"; staged files: kernel/capabilities/decision/executor.py, kernel/capabilities/decision/publish_command.py, run_kernel.py, tests/kernel/memory/test_learning_loop_e2e.py, tests/kernel/memory/test_publish_command_runnable.py, ticket. Probe script verify_precommit_active.py absent; probe skipped.
BLOCKED: check-root-files hook rejects new root file run_kernel.py (not in ALLOWED_ROOT_FILES in .leafcutter/scripts/commit_guardian/check_root_files.py). Commit not made; second hook failure, no further retry.
completion_manifest:
  pre_commit_hooks_pass:
    result: false
    reason: check-root-files rejects run_kernel.py at repo root
    remediation: add run_kernel.py to ALLOWED_ROOT_FILES or relocate launcher
  commit_message_valid: true
  ticket_staged: true

### 2026-10-02 15:00 — python-coder (status: ok)
feedback-id: fb_2026-10-02_0c28adfa
Owner decision applied: launcher moved by `git mv` to scripts/run_kernel.py (inserts repo root on sys.path, then runs kernel CLI). Printed command is `<python> <root>/scripts/run_kernel.py decisions publish --run-id <id>`. Quoting per M-1: quote only whitespace paths; when quoted and os.name == 'nt', prefix `& `; no-space form is plain. Added 4 tests (plain on nt/posix, nt quoted with `&`, posix quoted without `&`, scripts launcher path). test_publish_command_runnable + test_learning_loop_e2e: 17 passed; ruff clean. The e2e test already runs the printed command from a temp dir.

### 2026-10-02 15:30 — commit (status: ok)
feedback-id: (submit-failed)
Auto-authorized commit gate: subject "feat(kernel): make printed decisions-publish command runnable as shown"; staged files: kernel/capabilities/decision/executor.py, kernel/capabilities/decision/publish_command.py, scripts/run_kernel.py, tests/kernel/memory/test_learning_loop_e2e.py, tests/kernel/memory/test_publish_command_runnable.py, ticket. Probe passed.
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true

### 2026-10-06 23:10 — python-coder (status: ok)
feedback-id: fb_2026-10-06_2304303c
Follow-up on PR #999: the printed "publish writes it into" folder is now resolved by the same helper publish uses. Added MemoryConfig.decisions_folder(base) in kernel/config_memory.py; kernel/memory/cli.py run_decisions uses it, and publish_command.publish_folder(config) uses it with repo_root() as base (the printed command passes no --repo-root). executor passes ctx.config. How-to Step 1 quoted text updated to match the printed note. Regression test added: non-default memory.decisions_dir is named in the notice. kernel/memory + kernel/capabilities: 326 passed, 1 failed (test_host_operations: host.retrieval_needs, unrelated to this change); ruff clean, ast.parse ok.
