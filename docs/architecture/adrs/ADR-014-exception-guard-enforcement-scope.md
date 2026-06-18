---
title: "ADR-014: Exception-Handling Guard Enforcement Scope"
description: "Records two enforcement-scope decisions for the exception-handling pre-commit guard: subprocess calls become a mandatory I/O boundary (GE-108a), and only WARNING-or-higher logging on a real logger clears a blind-catch handler (GE-108b)."
type: "adr"
status: "accepted"
created: "2026-06-17"
last_updated: "2026-06-17"
deciders:
  - leafcutter-engineering-team
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/acceptance-criteria/guardrail-engine/GE-108-exception-hook-hardening/
related_code:
  - templates/commit-guardian/check_exception_handling.py
  - templates/commit-guardian/commit_guardian.json
---

# ADR-014: Exception-Handling Guard Enforcement Scope

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-06-17 |
| Deciders | leafcutter engineering team |
| Author | leafcutter engineering team |
| Supersedes | — |

## Context

The exception-handling pre-commit guard lives at
`templates/commit-guardian/check_exception_handling.py`. It enforces the project
Error Handling Policy (CLAUDE.md Rules 1 and 3). This ADR records two
enforcement-scope decisions that back acceptance criteria GE-108a and GE-108b in
[`docs/acceptance-criteria/guardrail-engine/GE-108-exception-hook-hardening/`](../../acceptance-criteria/guardrail-engine/GE-108-exception-hook-hardening/).

These decisions are follow-up work to GE-107, which made the same guard
production-only scoped (the production-only scoping decision shipped under PR #95).
This ADR **extends** that prior decision rather than reversing it: GE-107 narrowed
*where* the guard applies (production code only), and GE-108 broadens *what* the
guard detects within that scope.

Two specific gaps motivated this ADR:

1. **Subprocess calls are undetected.** CLAUDE.md Rule 1 explicitly names
   "subprocess calls" as external I/O that must be wrapped in `try/except`. The
   guard's `_IO_BOUNDARIES` table currently covers `requests.*`, builtin `open()`,
   and `cursor.execute`/`executemany`/`callproc` — but NOT subprocess.

2. **The blind-catch heuristic is over-permissive.** CLAUDE.md Rule 3 requires
   every `except` block to either log at WARNING or higher, or re-raise. The
   guard's `_handler_reraises_or_logs` heuristic accepts ANY call whose name is in
   `_LOG_CALL_NAMES` (`log`, `logger`, `logging`, `warn`, `warning`, `error`,
   `critical`, `exception`, `info`, `debug`, `print`) as "non-silent" handling.

## Decision

### Decision 1 — Subprocess calls are a mandatory I/O boundary (backs GE-108a)

The guard MUST treat subprocess spawning as an external I/O boundary. The detected
I/O-boundary set (and the `commit_guardian.json` `exception_handling.io_boundary_calls`
spec, which MUST be kept in parity with the code table) MUST be extended to include:

- `subprocess.run`
- `subprocess.Popen`
- `subprocess.call`
- `subprocess.check_call`
- `subprocess.check_output`
- `subprocess.getoutput`

An unwrapped call to any of these in production code MUST be reported as an IO-001
violation. The code table and the JSON spec MUST NOT drift apart; they are a single
logical list maintained in two locations.

### Decision 2 — Only WARNING-or-higher logging clears a blind-catch handler (backs GE-108b)

The `_handler_reraises_or_logs` heuristic MUST be tightened so that only genuine
WARNING / ERROR / CRITICAL / exception-level logging on a real logger object — or a
re-raise — clears a blind-catch handler. The current heuristic is over-permissive in
two ways, both of which this decision eliminates:

(a) A user-defined function coincidentally named `error()` / `info()` / `debug()`
    that is NOT a real logger currently clears the handler (a false negative caused by
    name coincidence). After this decision, name coincidence MUST NOT clear a handler.

(b) A handler whose only logging is `logger.debug()` / `logger.info()` / `print()` is
    currently accepted, despite being below the WARNING threshold Rule 3 requires.
    After this decision, DEBUG, INFO, and `print` MUST NOT clear a handler.

Detection MUST stay purely AST-based, resolving the logger object via attribute access.
There MUST NOT be a regex fallback.

## Consequences

This section records the false-positive tradeoff analysis for both decisions
explicitly — not a generic consequences paragraph — because the enforcement-scope
widening in each decision changes which existing code the guard will newly flag.

### Decision 1 — false-positive analysis (subprocess boundary)

**Risk:** The widened subprocess detection may flag intentionally-unwrapped
subprocess calls that already exist in the codebase.

**Mitigation (binding):** leafcutter's own codebase MUST commit cleanly after the
change is implemented (self-hosting non-regression). Any deliberately-unwrapped
subprocess call MUST either be wrapped in a typed `try/except` or explicitly exempted
via the guard's exemption mechanism before the change ships. The self-hosting clean
commit is the acceptance gate for the false-positive surface introduced by Decision 1.

### Decision 2 — false-positive analysis (WARNING+ threshold)

**Risk:** The WARNING+ threshold may flag handlers that legitimately log at INFO.

**Resolution (accepted):** This is an accepted consequence, not a defect. Rule 3 is
explicit that INFO is insufficient. Handlers that genuinely only warrant INFO-level
logging MUST either re-raise or be re-examined — the threshold tightening is the
intended behaviour, and any handler it newly flags was already non-compliant with
Rule 3.

### Operational consequences

- The guard and the `commit_guardian.json` spec must be edited together for Decision 1;
  a parity test or review step prevents code/spec drift.
- Decision 2 narrows what counts as compliant logging, so the change is gated on the
  same self-hosting clean-commit requirement: leafcutter's own handlers must pass the
  tightened heuristic before the change ships.

## Alternatives

### Decision 1 alternative — Leave subprocess out (status quo)

**Rejected.** Subprocess spawning is explicitly named as an external I/O boundary in
CLAUDE.md Rule 1. Leaving it undetected means the guard silently fails to enforce a
policy the project has already committed to in writing.

### Decision 2 alternative — Keep the name-based heuristic but exclude debug/info/print

Keep matching call names against `_LOG_CALL_NAMES` but drop `debug`, `info`, and
`print` from the set.

**Rejected.** This approach still leaves the guard vulnerable to name-coincidence
false negatives — any user-defined function named `warning()` would wrongly clear the
handler regardless of whether it is a real logger. Resolving the real-logger object via
AST attribute access is the robust fix; name-set pruning treats only the symptom.

## References

- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — the
  template/scripts build convention; relevant because the guard lives inside
  `templates/` and must remain self-hosting, which is also the acceptance gate for
  the false-positive analysis above.
- GE-107 prior work — the production-only scoping decision for the same guard (PR #95).
  This ADR extends that decision rather than reversing it.
- [GE-108 acceptance-criteria tree](../../acceptance-criteria/guardrail-engine/GE-108-exception-hook-hardening/) —
  the acceptance criteria (GE-108a, GE-108b) this ADR backs.
