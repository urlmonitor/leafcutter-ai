---
title: "Track: missing check_exception_handling.py causes TDD red-baseline failures"
status: todo
components:
  - commit_guardian
  - precommit_hooks
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - scripts/commit_guardian/check_exception_handling.py
  - unit_tests/commit_guardian/
agents:
  architect-review: not_needed
  test-writer: not_needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Track: missing check_exception_handling.py causes TDD red-baseline failures

## Actor / Goal

In order to restore a clean GREEN test baseline after EPIC-Defineabehavioronce,reusethespec
was merged, we need `scripts/commit_guardian/check_exception_handling.py` to be
implemented so that its TDD red-baseline stub tests pass.

## Context

During the post-merge baseline run for EPIC-Defineabehavioronce,reusethespec (PR #85,
merged 2026-06-17), 18 test failures were recorded. These were triaged and confirmed to
be pre-existing TDD red-baseline stubs written against unimplemented hooks — zero
regressions from the merged epic itself (`blocks_finalization = false`).

This ticket tracks one distinct root-cause category from that triage:

**Root cause:** The script `scripts/commit_guardian/check_exception_handling.py` is
referenced by the test suite but has not yet been authored. Tests for this hook were
written as TDD stubs (expected to run RED until implementation exists). The script
performs AST-based enforcement of:

- Ruff rule **E722** — bare `except:` clauses.
- Ruff rule **BLE001** — blind exception catch (`except Exception` without re-raise or log).
- Ruff rules **TRY*** (tryceratops family) — general try/except anti-patterns.
- **I/O boundary enforcement** — ensures all external I/O calls (`requests.*`, `open()`,
  `cursor.execute()`, subprocess) are wrapped in a typed `try/except` block.

The spec for this hook lives in `scripts/commit_guardian/commit_guardian.json` under the
`exception_handling` section. The enforcement policy is documented in the repo
`CLAUDE.md` Error Handling Policy section (four rules).

### Relationship to CLAUDE.md Error Handling Policy

The four rules in the repo CLAUDE.md ("External I/O must be wrapped", "Never bare except",
"Never silently swallow", "No try/except on pure internal functions") are the human-readable
expression of what `check_exception_handling.py` must enforce mechanically. This script
is the commit-time gate that prevents violations from entering the codebase.

### Failing test count

Approximately 18 tests in `unit_tests/commit_guardian/` fail RED because they import or
invoke `check_exception_handling` and the file does not exist. All are pre-existing TDD
stubs. This ticket's done state requires all of them to pass GREEN with no new failures.

## Acceptance Criteria

- [ ] AC-1: `scripts/commit_guardian/check_exception_handling.py` exists and is invocable as a pre-commit hook script via the standard `run_hook.py` entry point pattern used by sibling hooks.
- [ ] AC-2: The script uses AST analysis (not regex) to detect violations of Ruff rules E722, BLE001, and the TRY family in staged Python files.
- [ ] AC-3: The script detects bare `except:` clauses (E722) and exits non-zero, printing the offending file and line number.
- [ ] AC-4: The script detects blind exception catches (`except Exception` or `except BaseException`) where the except block neither logs at WARNING+ nor re-raises (BLE001), and exits non-zero.
- [ ] AC-5: The script detects external I/O calls (`requests.*`, `open()`, `cursor.execute()`, subprocess variants) not wrapped in a typed `try/except` block, and exits non-zero.
- [ ] AC-6: When no violations are found in staged files, the script exits 0 with no output.
- [ ] AC-7: All pre-existing TDD stub tests in `unit_tests/commit_guardian/` that reference `check_exception_handling` pass GREEN. No previously-passing tests regress.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | test_hook_invocable | check_exception_handling.py — entry point | |
| AC-2 | test_ast_analysis | check_exception_handling.py — AST walk | |
| AC-3 | test_bare_except_detected | check_exception_handling.py — E722 visitor | |
| AC-4 | test_blind_catch_detected | check_exception_handling.py — BLE001 visitor | |
| AC-5 | test_unwrapped_io_detected | check_exception_handling.py — I/O boundary visitor | |
| AC-6 | test_clean_file_exits_zero | check_exception_handling.py — clean path | |
| AC-7 | existing TDD stubs | check_exception_handling.py | |

## Sign-offs

- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

### 2026-06-17 00:00 — BrainCandy (status: ok)
feedback-id: none
Ticket created as a tracking record for the `check_exception_handling.py` missing-script
root-cause category from the EPIC-Defineabehavioronce,reusethespec post-merge baseline
triage. `blocks_finalization = false` for the merged epic; this ticket captures the
follow-up implementation work as a standalone inbox item.

## Implementation Tasks

- [ ] Read `scripts/commit_guardian/commit_guardian.json` `exception_handling` section to extract the full spec.
- [ ] Read sibling hooks (e.g. `check_contract_shrinking.py`, `check_placeholder_defaults.py`) to match the `run_hook.py` entry-point pattern and AST-walk conventions.
- [ ] Implement `scripts/commit_guardian/check_exception_handling.py`:
  - AST visitor detecting bare `except:` (E722).
  - AST visitor detecting blind catches without log/re-raise (BLE001/TRY).
  - AST visitor detecting external I/O calls outside `try/except` blocks.
  - Exit 0 on clean, non-zero with line-level messages on violations.
- [ ] Run the full `unit_tests/commit_guardian/` suite and confirm all previously-failing stubs are now GREEN.
- [ ] Confirm no previously-passing tests regressed.

## Out of Scope

- Modifying the existing TDD stub tests. The stubs define the contract; the implementation must satisfy them as-is.
- Changes to `commit_guardian.json` hook registration (the hook is already registered; the script file is the only missing artifact).
- Extending enforcement to non-Python file types.

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The new script is additive — removing it reverts to the pre-existing state (failing stubs, no runtime enforcement). No data or schema changes.
- Risk of regressions: low. The script is invoked only at commit time on staged files; it cannot affect runtime behaviour. The main regression risk is a false-positive that blocks legitimate commits — mitigated by the existing TDD stubs which cover both violation and clean-file paths.
