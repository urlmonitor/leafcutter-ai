---
title: "Done-proof launches vitest on Windows, so JS-covered ACs can be proven there"
status: todo
components:
  - build_orchestration
created: 2026-10-08
depends_on: []
priority: high
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: contract_boundary
roadmap_phase: phase_1
advances_current_outcome: true
tags:
  - done-proof
  - vitest
  - windows
  - portability
  - bo-2500
last_updated: 2026-10-08
files_touched:
  - scripts/ac_store/_done_proof_phase_helpers.py
  - scripts/ac_store/done_proof.py
  - unit_tests/ac_store/test_done_proof_js_integration.py
  - unit_tests/ac_store/test_done_proof_composite_js.py
  - unit_tests/ac_store/test_done_proof_js.py
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# Done-proof launches vitest on Windows, so JS-covered ACs can be proven there

## Actor / Goal
In order that a JS-covered acceptance criterion can be proven done on a Windows host, we need
the done-proof's vitest seam to start vitest in a way Windows can execute, so that the proof
reaches a real PASSED/FAILED verdict instead of always failing closed with `[WinError 193]`.

## Context
- **The defect.** `run_vitest_and_parse` (`scripts/ac_store/done_proof.py:742`) resolves
  `<project>/node_modules/.bin/vitest` (:794) and launches it directly
  (`_build_vitest_command`, `_execute_vitest` in `scripts/ac_store/_done_proof_phase_helpers.py`
  :355-376 and :379). On every platform that file is npm's POSIX `#!/bin/sh` shim. Windows'
  `CreateProcess` rejects it, so the seam raises
  `JsRunnerUnavailable: vitest OS error on launch: [WinError 193]` (verified 2026-10-06 on
  Windows 11 with the toolchain installed, in TICKET-20261006-CiShardsInstallWebToolchain).
- **Effect.** The done-proof oracle (BO-2500) fails closed for every JS-covered AC on a Windows
  host: the commit-time `check-done-proof` hook and `verify_done_eligible`. A correct, tested
  feature cannot be marked done there.
- **Already noted, not ticketed.** TICKET-20261006-CiShardsInstallWebToolchain, "Out of Scope":
  "Making `run_vitest_and_parse` launch on Windows (resolve `vitest.cmd`, or run
  `node vitest.mjs`) ... needs its own ticket." That ticket added the Windows-only
  `@unittest.skipIf(os.name == "nt", ...)` on
  `unit_tests/ac_store/test_done_proof_js_integration.py` (:64-70) for this very reason.
- **A launch that works on Windows is already proven.**
  `unit_tests/ac_store/test_done_proof_composite_js.py:203-225` swaps only the launcher for
  `node <leafcutter-web>/node_modules/vitest/vitest.mjs` and keeps the production arguments,
  parser and eligibility logic. It is green on Windows. That fixture builds its own
  `node_modules/.bin/vitest` shim, so it must follow whatever resolution the fix chooses.
- **Size.** `done_proof.py` measures 1170 lines against the 400-line `.py` limit (ratchet:
  leave it shorter than at HEAD). `_done_proof_phase_helpers.py` measures 358, which leaves 42
  lines of headroom. Put the change in the helper.

## Acceptance Criteria
- [ ] AC-1: On Windows with the web toolchain installed, `run_vitest_and_parse` on a real passing
  `.test.ts` returns `PASSED`, and on a real failing one returns `FAILED`, with no
  `JsRunnerUnavailable`.
- [ ] AC-2: The launch resolves the same vitest install on Windows and Linux (for example
  `node <project>/node_modules/vitest/vitest.mjs`), with no platform-specific shell shim. The
  docstrings and messages that name `node_modules/.bin/vitest` say what is launched now.
- [ ] AC-3: A missing runtime still raises `JsRunnerUnavailable` with an actionable message on
  both platforms: `node` not on PATH, and the vitest entry point not installed.
- [ ] AC-4: The Windows `skipIf` on `test_done_proof_js_integration.py` is removed. Both of its
  tests run and pass on Windows and on the Linux CI shards.
- [ ] AC-5: `test_done_proof_composite_js.py` and `test_done_proof_js.py` pass on both platforms
  with their fixtures adjusted to the new resolution. No fixture fakes an outcome.

## Test Requirements

```yaml
tests:
  - name: test_absolute_paths_return_passed
    location: unit_tests/ac_store/test_done_proof_js_integration.py
    type: integration
    covers: [AC-1, AC-4]
    description: |
      Existing test in TestRunVitestRealInvocation; remove the Windows skip. Red on Windows
      today with [WinError 193].
  - name: test_relative_paths_are_resolved_before_launch
    location: unit_tests/ac_store/test_done_proof_js_integration.py
    type: integration
    covers: [AC-4]
    description: |
      Existing test in TestRunVitestRealInvocation; must pass on Windows and Linux.
  - name: test_failing_ts_file_returns_failed
    location: unit_tests/ac_store/test_done_proof_js_integration.py
    type: integration
    covers: [AC-1]
    description: |
      New: a real .test.ts with a failing assertion (in a temp project using the installed
      vitest) yields FAILED through run_vitest_and_parse on both platforms.
  - name: test_missing_node_or_vitest_entry_raises_runner_unavailable
    location: unit_tests/ac_store/test_done_proof_js.py
    type: unit
    covers: [AC-3]
    description: |
      With node absent from PATH, and separately with the vitest entry point absent, the seam
      raises JsRunnerUnavailable naming what to install.
```

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_absolute_paths_return_passed, test_failing_ts_file_returns_failed (Windows run) | | |
| AC-2 | review + TestRunVitestRealInvocation | | |
| AC-3 | test_missing_node_or_vitest_entry_raises_runner_unavailable | | |
| AC-4 | test_done_proof_js_integration.py (Windows and CI) | | |
| AC-5 | test_done_proof_composite_js.py, test_done_proof_js.py | | |

## Comments

_(Append-only log — leave blank when authoring.)_

## Implementation Tasks
- [ ] `_ensure_vitest_binary` / `_build_vitest_command`: resolve `node` and the vitest JS entry
  point and build `[node, <vitest.mjs>, "run", "--reporter=json", ...]`.
- [ ] Update the messages and docstrings in `done_proof.py` without growing it.
- [ ] Remove the Windows skip; adjust the composite fixture's shim to the new resolution.
- [ ] Run the three test files on Windows and Linux.

## Risk & Safety
- Touches money? No.
- Touches data? No. It changes how the proof oracle starts vitest. A wrong resolution fails
  closed (`JsRunnerUnavailable`), never as a false PASSED.
- Reversibility: revert the commit.

## Out of Scope
- Installing the web toolchain in CI (done by TICKET-20261006-CiShardsInstallWebToolchain) and
  in the durations workflow (TICKET-20261008-BuildPipelineHygiene).
