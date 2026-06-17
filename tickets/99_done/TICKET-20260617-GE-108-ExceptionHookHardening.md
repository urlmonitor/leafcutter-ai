---
title: "Harden check_exception_handling: subprocess boundary, logging-heuristic accuracy, tuple label"
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
requires_adr: true
files_touched:
  - templates/commit-guardian/check_exception_handling.py
  - templates/commit-guardian/commit_guardian.json
  - unit_tests/commit_guardian/test_check_exception_handling.py
agents:
  architect-review: not_needed
  adr-author: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: not_needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
ac_coverage: 0/10
---

# Harden check_exception_handling: subprocess boundary, logging-heuristic accuracy, tuple label

## Actor / Goal

In order to close three deferred robustness and accuracy gaps in the exception-handling
pre-commit hook, we need to extend `_IO_BOUNDARIES` to cover subprocess calls, tighten
the blind-catch logging heuristic to require WARNING+, and fix the BLE001 tuple-exception
message so that the hook faithfully enforces the project Error Handling Policy (CLAUDE.md
Rules 1 and 3).

## Context

This ticket is the direct follow-up to GE-107 (PR #95), which fixed two separate findings
from the same hook (cursor-receiver false-positive and OSError crash on unreadable paths).
Those two are resolved and out of scope here.

The three findings below were explicitly deferred from GE-107 because each involves a
design/spec decision, not a mechanical one-file fix. They were surfaced by manual testing
of the hook after GE-107 shipped.

### Build convention (MANDATORY)

The committable source of truth is `templates/commit-guardian/check_exception_handling.py`
and `templates/commit-guardian/commit_guardian.json`. The `scripts/commit_guardian/` copies
are gitignored build output synced by `build.py`. Any fix MUST edit the template files and
then rebuild:

```bash
python leafcutter/scripts/build.py
```

Do NOT edit `scripts/commit_guardian/` directly — those changes will be overwritten on the
next build.

### Related policy

CLAUDE.md "Error Handling Policy":

- **Rule 1**: All calls to `requests.*`, `open()`, `cursor.execute()`, subprocess calls,
  and any other external I/O must be wrapped in `try/except <SpecificExceptionType>`.
- **Rule 3**: Every `except` block must either log at WARNING or higher, or re-raise.

### Finding 1 — Subprocess I/O boundary not detected (highest value, policy/spec mismatch)

`_IO_BOUNDARIES` covers `requests.*`, builtin `open()`, and `cursor.execute`/`executemany`/
`callproc` — but NOT `subprocess`. Calling `subprocess.run(...)` or `subprocess.Popen(...)`
unwrapped (no surrounding `try/except`) produces exit 0 / no violation.

CLAUDE.md Rule 1 explicitly names "subprocess calls" as external I/O that must be wrapped.
The JSON spec (`commit_guardian.json`, `exception_handling` → `io_boundary_calls`) also
omits subprocess, so the implementation matches its spec — but the spec is narrower than the
written policy.

Decision needed: extend `_IO_BOUNDARIES` (and the JSON spec) to cover `subprocess.run`,
`subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`,
`subprocess.getoutput`, weighing false-positive risk against policy compliance. This decision
MUST be recorded in an ADR before coding begins (see Architecture Plan).

### Finding 2 — Blind-catch logging heuristic is name-based and over-permissive (false negatives)

`_handler_reraises_or_logs` treats ANY call whose function/attribute name is in
`_LOG_CALL_NAMES` (`log`, `logger`, `logging`, `warn`, `warning`, `error`, `critical`,
`exception`, `info`, `debug`, `print`) as "non-silent" handling. Two problems:

(a) A blind `except Exception:` whose body only calls a user-defined function coincidentally
named `error()`/`info()`/`debug()` — NOT a real logger — is wrongly accepted as compliant
(false negative, slips through BLE001/TRY).

(b) A handler whose only logging call is `logger.debug(...)` or `logger.info(...)` or
`print(...)` is accepted, violating Rule 3 (must log at WARNING+).

Decision needed: tighten the heuristic so only genuine logging at WARNING+ (or a re-raise)
counts as non-silent handling. The chosen threshold must be recorded in the same ADR as
Finding 1.

### Finding 3 — Tuple exception type reports imprecise label (cosmetic, rides with 1 and 2)

For `except (ValueError, Exception):`, the BLE001 violation message reports the caught type
as just `"Exception"` (the `ast.Name` fallback) rather than the full tuple. Detection is
correct (it IS flagged) and line/col are correct — only the human-readable message is
imprecise. Low-priority polish item, bundled here to avoid a separate micro-ticket.

### Architectural context

The hook uses `ast` module walking across staged Python files only (no full-repo scan).
It exits 0 when clean, non-zero when any violation is found. Detection must remain
purely AST-based — no regex fallback. The self-hosting constraint (Rule 4 analogy) means
the widened subprocess detection must not produce violations on the leafcutter codebase's
own legitimate subprocess usage.

## Architecture Plan

### ADRs

- `ADR-XXX — Exception-handling hook enforcement scope: subprocess as mandatory I/O boundary and WARNING+ logging for blind-catch handlers` — new ADR to be authored before coding begins (covers Findings 1 and 2; Finding 3 requires no ADR).

## Agent Contracts

### adr-author

- [ ] AC-1: ADR authored at `docs/architecture/adrs/` documenting the decision to (a) treat `subprocess.{run,Popen,call,check_call,check_output,getoutput}` as mandatory I/O boundaries under Rule 1 and (b) require WARNING-or-higher logging (not DEBUG/INFO/print) for a blind-catch handler to be considered non-silent under Rule 3.
- [ ] AC-2: ADR records the false-positive tradeoffs for each decision: subprocess detection may flag intentionally-unwrapped subprocess calls; WARNING+ threshold may flag handlers that legitimately log at INFO.

**Delivers to python-coder:**
```json
{
  "subprocess_call_set": ["subprocess.run", "subprocess.Popen", "subprocess.call", "subprocess.check_call", "subprocess.check_output", "subprocess.getoutput"],
  "logging_threshold": "WARNING",
  "false_positive_mitigations": "documented in ADR body"
}
```

**Depends on:** none (authors ADR from policy documents only)

### test-writer

- [ ] AC-3: Failing test (RED before python-coder change): unwrapped `subprocess.run` at module scope is reported as an I/O-boundary violation.
- [ ] AC-4: Failing test (RED before python-coder change): unwrapped `subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`, `subprocess.getoutput` each produce a violation; the same calls inside a `try/except` produce no violation.
- [ ] AC-5: Failing test (RED before python-coder change): `commit_guardian.json` `io_boundary_calls` spec lists the subprocess call forms (spec/impl parity assertion).
- [ ] AC-6: Failing test (RED before python-coder change): a blind `except Exception:` whose body only calls a user-defined function named `error()` or `debug()` (not a logger) is reported as a silent-handler violation.
- [ ] AC-7: Failing test (RED before python-coder change): a blind handler whose only logging is `logger.debug(...)` / `logger.info(...)` / `print(...)` is reported as a violation; the same handler with `logger.warning(...)` or a re-raise passes.
- [ ] AC-8: Failing test (RED before python-coder change): BLE001 message for `except (ValueError, Exception):` contains the full tuple text, not just `"Exception"`.

**Delivers to python-coder:** red test suite pinning the eight success-criteria cases. GE-107 regression cases (cursor receiver false-positive, OSError crash) must remain GREEN throughout.

**Depends on:** adr-author AC-1, AC-2 (to know the agreed subprocess set and logging threshold before authoring tests)

### python-coder

- [ ] AC-9: `_IO_BOUNDARIES` in `templates/commit-guardian/check_exception_handling.py` is extended to detect `subprocess.run`, `subprocess.Popen`, `subprocess.call`, `subprocess.check_call`, `subprocess.check_output`, `subprocess.getoutput` called outside a `try/except` block. The `io_boundary_calls` entry in `templates/commit-guardian/commit_guardian.json` is updated with the same call set. Both template files are rebuilt via `python leafcutter/scripts/build.py` and the build output matches the templates.
- [ ] AC-10: `_handler_reraises_or_logs` is tightened so that (a) user-defined functions named `error()`/`debug()`/`info()` that are NOT real logger calls do NOT satisfy the "non-silent" predicate, and (b) logging calls below WARNING (`debug`, `info`, `print`) do NOT satisfy the predicate — only `logger.warning()`+, `logging.warning()`+, re-raises, and `logger.exception()` satisfy it. All test-writer red cases (AC-3 through AC-8) pass GREEN. GE-107 regression cases remain GREEN. The leafcutter codebase itself commits cleanly after the change (no false-positive self-hosting violations).

**Delivers to pr-reviewer:** updated template + built scripts + test results.

**Depends on:** adr-author AC-1, AC-2 (subprocess set and logging threshold); test-writer AC-3 through AC-8 (red baseline).

### pr-reviewer

Review the diff for:

- Template/scripts parity: `templates/commit-guardian/check_exception_handling.py` and `commit_guardian.json` edits are reflected identically in `scripts/commit_guardian/` after build.
- Rule 1 alignment: subprocess is now detected as mandatory I/O boundary.
- Rule 3 alignment: WARNING+ is enforced; DEBUG/INFO/print no longer pass the handler predicate.
- Self-hosting non-regression: the leafcutter codebase's own subprocess usage (if any) is either wrapped (passes) or explicitly documented in the ADR as an exempted pattern.
- GE-107 regressions: cursor false-positive and OSError crash fixes remain intact.
- AC-3 through AC-10 are all GREEN.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | — | adr-author: ADR document | |
| AC-2 | — | adr-author: ADR tradeoff section | |
| AC-3 | test_subprocess_run_unwrapped_violation | python-coder: _IO_BOUNDARIES extension | |
| AC-4 | test_subprocess_variants_wrapped_clean / test_subprocess_variants_unwrapped_violation | python-coder: _IO_BOUNDARIES extension | |
| AC-5 | test_json_spec_lists_subprocess_forms | python-coder: commit_guardian.json update | |
| AC-6 | test_user_defined_error_fn_not_silent | python-coder: _handler_reraises_or_logs tightened | |
| AC-7 | test_debug_logging_is_violation / test_warning_logging_passes | python-coder: _handler_reraises_or_logs tightened | |
| AC-8 | test_tuple_exception_blemessage_full_tuple | python-coder: BLE001 message construction | |
| AC-9 | AC-3, AC-4, AC-5 | python-coder: templates + build | |
| AC-10 | AC-6, AC-7, AC-8 | python-coder: templates + build | |

## Sign-offs

- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Implementation Tasks

- [ ] adr-author: Author `ADR-XXX — Exception-handling hook enforcement scope` covering the subprocess call set decision and the WARNING+ logging threshold decision. Record false-positive tradeoffs for each. The ADR file must exist before test-writer or python-coder begin.
- [ ] test-writer: Read the ADR. Author red (failing) test cases AC-3 through AC-8 in `unit_tests/commit_guardian/test_check_exception_handling.py`. Run the suite to confirm new tests are RED and all GE-107 cases remain GREEN. Capture red_baseline.
- [ ] python-coder: Read the ADR and the red baseline. Edit `templates/commit-guardian/check_exception_handling.py`:
  - Extend `_IO_BOUNDARIES` with the six subprocess call forms from the ADR.
  - Tighten `_handler_reraises_or_logs` to require WARNING+ on a real logger object (not a name-only check) or a re-raise.
  - Fix the BLE001 message construction to render the full tuple for tuple exception types.
- [ ] python-coder: Edit `templates/commit-guardian/commit_guardian.json` to add the subprocess call forms to `io_boundary_calls`.
- [ ] python-coder: Run `python leafcutter/scripts/build.py` to sync the gitignored `scripts/commit_guardian/` copies.
- [ ] python-coder: Run `unit_tests/commit_guardian/test_check_exception_handling.py` — confirm AC-3 through AC-10 are GREEN and no GE-107 regressions.
- [ ] python-coder: Verify the leafcutter codebase still commits cleanly (no false-positive self-hosting violations from the widened subprocess detection).
- [ ] pr-reviewer: Review diff for template/scripts parity, Rule 1 + Rule 3 alignment, self-hosting non-regression, GE-107 regression safety.

## Out of Scope

- The two findings already fixed in GE-107 (PR #95): cursor-receiver false-positive and OSError crash on unreadable path.
- Non-Python file types.
- Changing or de-duplicating the template/scripts build layout (pre-existing convention, tracked separately).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? The template changes are reversible by reverting the template files and rebuilding. The ADR is append-only (new file). Tests are additive.
- False-positive risk (Finding 1): the widened subprocess detection may flag existing legitimate subprocess calls in the codebase that are currently unwrapped. The ADR must document the agreed exemption strategy. Mitigation: the self-hosting non-regression check in AC-10 must pass before PR merge.
- False-positive risk (Finding 2): tightening the heuristic to WARNING+ may flag handlers that legitimately log at INFO. The ADR must document the threshold decision. Mitigation: AC-7 covers the boundary case.
- Finding 3 carries no risk (message-only change, no detection-logic change).
