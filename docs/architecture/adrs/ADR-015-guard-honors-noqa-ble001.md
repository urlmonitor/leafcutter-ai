---
title: "ADR-015: Exception-Handling Guard Honors Inline `# noqa: BLE001` Suppression"
description: "Records the decision to teach check_exception_handling.py to honor inline `# noqa: BLE001` suppression comments, scoped per-line and per-violation-code to match Ruff semantics, resolving the GE-108b self-hosting regression where the widened guard flagged leafcutter's own intentionally-blind handlers."
type: "adr"
status: "active"
created: "2026-06-18"
last_updated: "2026-06-18"
deciders:
  - leafcutter-engineering-team
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/architecture/adrs/ADR-014-exception-guard-enforcement-scope.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
related_code:
  - templates/commit-guardian/check_exception_handling.py
  - templates/scripts/commit_guardian/check_exception_handling.py
  - unit_tests/commit_guardian/test_check_exception_handling.py
---

# ADR-015: Exception-Handling Guard Honors Inline `# noqa: BLE001` Suppression

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-06-18 |
| Deciders | leafcutter engineering team |
| Author | leafcutter engineering team |
| Supersedes | — |

## Context

This ADR is a direct follow-up to
[ADR-014](ADR-014-exception-guard-enforcement-scope.md) Decision 2 (GE-108b),
which tightened `_handler_reraises_or_logs` in
`templates/commit-guardian/check_exception_handling.py` so that a blind
`except Exception:` is cleared only by genuine WARNING-or-higher logging on a
real logger object, or a re-raise. That tightening is correct and is not
reversed here.

Tightening the heuristic surfaced a **self-hosting regression** (filed as
TICKET-20260618-GE-108b-BLE001-SelfHosting-Regression, the follow-up to
EPIC-Exceptionhandlingguardenforcestheerror, PR #104). The widened guard now
flags pre-existing, intentionally-blind `except Exception:` handlers across
leafcutter's own production scripts — 14 originally, 12 remaining after PR #104's
autofix incidentally cleared 2.

### The core design gap

Several of the flagged handlers carry `# noqa: BLE001` — the team explicitly told
**Ruff** to allow them. But `check_exception_handling.py` (the custom AST guard)
**does not honor `# noqa` comments at all**. This is a silent contract mismatch:
a contributor who adds `# noqa: BLE001` expecting both Ruff and the pre-commit
guard to be suppressed will be surprised at commit time once the widened guard is
deployed. Ruff's CI gate ("Lint (ruff)") honors `# noqa`, so CI stays green —
the regression is purely a local-commit-time concern that activates the moment
`build.py` deploys the widened guard. The deployed
`.leafcutter/scripts/commit_guardian/check_exception_handling.py` is still the
stale pre-GE-108 version, which is why the regression is latent rather than
already-blocking.

The ticket offered three options: (1) honor `# noqa: BLE001` in the guard,
(2) wrap or annotate every flagged handler to make it genuinely compliant, or
(3) a hybrid of the two. This ADR records the chosen option.

## Decision

The guard MUST honor an inline `# noqa: BLE001` suppression comment and suppress
the BLE001 (blind-except) violation for that handler, aligning the custom AST
guard with Ruff's suppression model. The contract is:

1. **Per-line scope.** A `# noqa: BLE001` comment suppresses a BLE001 violation
   only when it appears on the **same physical source line** as the flagged
   construct, exactly as Ruff resolves `# noqa` placement. A comment on an
   unrelated line MUST NOT suppress a violation elsewhere.

2. **Per-violation-code scope.** The suppression MUST be scoped to the specific
   violation code named in the comment. A `# noqa: BLE001` comment suppresses
   **only** BLE001; it MUST NOT suppress any other guard violation (for example,
   it MUST NOT suppress an IO-001 unwrapped-I/O finding). Suppression of a
   different code requires that code to be named explicitly (e.g.
   `# noqa: BLE001, IO-001`).

3. **No blanket suppression.** A bare `# noqa` with no code list MUST NOT be
   honored by this guard as a blanket suppressor of BLE001. The guard honors
   only code-qualified suppressions. This prevents `# noqa` parsing from being
   abused to silence the guard wholesale.

4. **Detection stays AST-based.** Honoring `# noqa` MUST be implemented by
   reading the source line associated with the AST node's location; it MUST NOT
   reintroduce a regex-based detection path for the violation itself (consistent
   with ADR-014 Decision 2).

The code table and the `commit_guardian.json` spec remain a single logical
list maintained in two locations, per ADR-014; the noqa-honoring behavior
applies uniformly regardless of which boundary or heuristic produced the
candidate BLE001 violation.

## Consequences

### Positive

- **Closes the contract mismatch at the root.** A contributor who writes
  `# noqa: BLE001` now gets consistent behavior from both Ruff and the custom
  pre-commit guard. The surprising divergence at commit time is eliminated.
- **Resolves the self-hosting regression without touching production logic.**
  The 12 remaining flagged handlers that carry (or are given) a `# noqa: BLE001`
  comment stop blocking commits once `build.py` deploys the widened guard. No
  behavior-changing edits to those handlers are required by this decision.
- **Single, low-risk change site.** The fix lives in the guard's source-line
  resolution and is mirrored across the two template copies plus its test.

### Negative / accepted tradeoffs

- **Suppression is now possible by annotation.** A contributor can silence a
  genuine BLE001 by adding `# noqa: BLE001`. This is an accepted consequence: it
  mirrors Ruff's existing, already-trusted model exactly, and the annotation is
  explicit, greppable, and reviewable in diff. It is strictly less permissive
  than the pre-GE-108 guard, which silently accepted these handlers regardless.

### Operational

- **No change to genuinely non-compliant handler detection.** A blind
  `except Exception:` with **no** `# noqa: BLE001` comment and no WARNING+
  logging or re-raise MUST still be flagged. The per-code, per-line scoping
  guarantees the suppression is narrow.
- **noqa parsing cannot be abused to blanket-suppress.** Because only
  code-qualified `# noqa: BLE001` on the matching line is honored (Decision
  points 2 and 3), the mechanism cannot silence the guard wholesale or suppress
  unrelated violations such as IO-001.
- **Test coverage is mandatory.** The three acceptance scenarios — deploy does
  not block on annotated handlers, annotated handlers emit no BLE001, and
  un-annotated non-compliant handlers still emit BLE001 — must be covered in
  `unit_tests/commit_guardian/test_check_exception_handling.py`.
- The two template copies (`templates/commit-guardian/...` and
  `templates/scripts/commit_guardian/...`) MUST be edited together; a parity
  step prevents drift, consistent with ADR-014.

## Alternatives

### Option 2 — Wrap or annotate each flagged handler to make it compliant

Make every flagged blind handler genuinely compliant by adding WARNING+ logging
or a re-raise, removing all reliance on suppression.

**Rejected.** This is the more invasive path: it touches roughly ten files of
pre-existing handler debt and changes the runtime behavior of code that was
deliberately written to swallow exceptions. It also does not close the underlying
contract gap — a future contributor adding `# noqa: BLE001` would still be
surprised that the custom guard ignores it. It treats the symptom (the specific
12 handlers) rather than the root cause (the guard's divergence from Ruff).

### Option 3 — Hybrid: honor `# noqa` AND fix handlers that should be compliant

Honor `# noqa: BLE001` (Option 1) and additionally rewrite the subset of flagged
handlers that genuinely ought to log or re-raise.

**Rejected for this decision's scope.** The hybrid bundles a root-cause fix with
discretionary per-handler refactoring of pre-existing debt. Combining them in one
change widens the blast radius and couples a mechanical guard fix to subjective
judgments about which handlers "should" be compliant. Honoring `# noqa: BLE001`
(Option 1) fully resolves the regression on its own; any genuinely-warranted
handler hardening can be tracked and done separately without blocking this fix.

## References

- [ADR-014 — Exception-Handling Guard Enforcement Scope](ADR-014-exception-guard-enforcement-scope.md) —
  Decision 2 (GE-108b) is the tightening this ADR resolves the regression for;
  this ADR amends the guard's behavior without reversing that decision.
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — the
  template/scripts build convention; the self-hosting clean-commit requirement is
  what makes this regression a release gate.
- TICKET-20260618-GE-108b-BLE001-SelfHosting-Regression — the originating ticket,
  filed from a post-drive spot-check of EPIC-Exceptionhandlingguardenforcestheerror
  (PR #104).
