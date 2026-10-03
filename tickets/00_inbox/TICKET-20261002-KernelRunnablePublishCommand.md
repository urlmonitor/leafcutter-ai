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
  test-writer: needed
  python-coder: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Kernel: the printed decisions-publish command runs as shown

## Actor / Goal
In order that the owner can publish a staged decision record by copying the command the kernel prints, we need that command to work as printed.

## Context
- **Live reproduction (2026-10-02):** the staged-record limitation printed `publish it for review with: python -m kernel decisions publish --run-id run-49c4f5e97f2d41d6`. Run in the owner's PowerShell, it failed with `C:\Python314\python.exe: No module named kernel`: plain `python` is the system interpreter, without the project venv or the kernel's `PYTHONPATH`.
- The command also writes into the kernel checkout's `docs/decisions/`, which the message does not say.
- **Second reproduction (2026-10-02, run `run-3bba494c7c9b48ce`):** publishing into another
  worktree with `--repo-root <worktree>` failed with "no staged decision record for this run".
  - Cause: `kernel/memory/cli.py:83-99` resolves the run root relative to `--repo-root`
    (`resolve_run_root(config, base)`), so the staged record is looked for in the target
    worktree.
  - It worked only with a `--config` override that sets an absolute `paths.run_root`.

## Scope (no acceptance criteria by user decision)
- The printed command names the interpreter the kernel itself runs under (`sys.executable`), and the module path or a documented wrapper, so it works copied verbatim from any shell. It also states the folder it writes to.
- `--repo-root` names only the target store. The run root keeps resolving from the kernel
  checkout, or comes from a separate `--run-root`. A test publishes a fixture run into a
  different repo root.
- Tests: the limitation text contains `sys.executable`, and the path needed to import `kernel`; a smoke test runs the printed command in a subprocess from an unrelated directory against a fixture run and gets a JSON result.

## Comments
