---
title: "Resolve GE-108b BLE001 self-hosting regression: guard flags pre-existing blind-except handlers (and ignores # noqa: BLE001)"
status: todo
components:
  - commit_guardian
  - precommit_hooks
created: 2026-06-18
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: true
files_touched:
  - templates/commit-guardian/check_exception_handling.py
  - templates/scripts/commit_guardian/check_exception_handling.py
  - unit_tests/commit_guardian/test_check_exception_handling.py
agents:
  architect-review: not_needed
  adr-author: needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  architecture-diagram-author: not_needed
---

# Resolve GE-108b BLE001 self-hosting regression

## Actor / Goal

As a leafcutter contributor, I need the tightened exception-handling guard
(GE-108b) to not block commits on leafcutter's own pre-existing, intentionally
blind exception handlers — so that deploying the widened guard via `build.py`
does not break the repo's own commit flow.

## Context

This is the follow-up to EPIC-Exceptionhandlingguardenforcestheerror (PR #104),
filed from a post-drive spot-check.

GE-108b tightened `_handler_reraises_or_logs` so that a blind `except Exception:`
is cleared only by genuine WARNING+ logging on a real logger (attribute form) or
a re-raise. This is correct per ADR-014 Decision 2. **But** it surfaced a
self-hosting regression: the widened guard now flags **14 pre-existing blind
`except Exception:` handlers** across leafcutter's own production scripts. Two of
those (ac_prioritizer.py:290, emit_hook_finding.py:62) were incidentally cleared
during the PR #104 commit autofix; **12 remain**.

### The core design gap

Several of the flagged handlers carry `# noqa: BLE001` — the team explicitly told
**Ruff** to allow them. But `check_exception_handling.py` (the custom AST guard)
**does not honor `# noqa` comments at all**. This is a silent contract mismatch:
a contributor who adds `# noqa: BLE001` expecting both Ruff and the pre-commit
guard to be suppressed will be surprised at commit time once the widened guard is
deployed.

### Why this isn't blocking right now

The deployed `.leafcutter/scripts/commit_guardian/check_exception_handling.py`
is still the stale pre-GE-108 version, so these handlers are not yet flagged in
practice. The regression activates the moment `build.py` deploys the widened
guard. PR #104's CI gate is "Lint (ruff)", which honors `# noqa`, so CI is green —
this is purely a local-commit-time concern.

### Known flagged handlers (run the guard for the authoritative list)

As of 2026-06-18, the widened guard flags blind-except handlers in (non-exhaustive,
12 remaining after the PR #104 autofix cleared 2):

- scripts/build_phases.py:325 (# noqa: BLE001)
- scripts/seed_project_docs.py:56
- scripts/injection_builders.py:143
- scripts/build_roadmap_phase.py:95
- scripts/ticket_prioritizer.py:88
- scripts/build_propagation_audit.py:353
- scripts/bootstrap_install.py:97
- scripts/build_helpers.py:202, 256, 284
- scripts/worktree/sweep_processes.py:113 (# noqa: BLE001)

(Re-run `check_exception_handling.py` across `scripts/**/*.py` to regenerate the
current list — line numbers drift.)

## Decision needed (ADR)

Choose and record in an ADR (amend ADR-014 or author a new one):

1. **Honor `# noqa: BLE001` (and IO-001) in the guard** — teach
   check_exception_handling.py to skip a violation when the handler/line carries a
   matching `# noqa` comment, aligning the custom guard with Ruff's suppression
   model. (Recommended starting point — closes the contract mismatch at the root.)
2. **Wrap/annotate each flagged handler** — make every blind handler compliant
   (log WARNING+ or re-raise), removing reliance on suppression. More invasive;
   touches ~10 files of pre-existing debt.
3. **Hybrid** — honor noqa AND fix the handlers that should genuinely be compliant.

## Acceptance Criteria

```gherkin
Scenario: Deploying the widened guard does not block commits on leafcutter's own code
  Given the widened GE-108b exception-handling guard is built and deployed via build.py,
  When a contributor stages and commits any of leafcutter's own production scripts
    that contain a pre-existing intentionally-blind exception handler,
  Then the check-exception-handling pre-commit hook does not block the commit on
    account of those pre-existing handlers.

Scenario: The guard honors inline suppression consistent with Ruff (if option 1/3 chosen)
  Given a blind `except Exception:` handler annotated with `# noqa: BLE001`,
  When the exception-handling guard analyses the file,
  Then no BLE001 violation is emitted for that handler,
    matching Ruff's suppression behavior.

Scenario: Genuinely non-compliant handlers are still flagged
  Given a blind `except Exception:` handler with NO suppression comment and no
    WARNING+ logging or re-raise,
  When the guard analyses the file,
  Then a BLE001 violation is still emitted.
```

## Sign-offs

- [ ] adr-author
- [ ] test-writer
- [ ] python-coder
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments

## Out of Scope

- The 23 pre-existing `open()` IO-001 detections (separate pre-existing debt,
  predates GE-108 — track separately if desired).
- The GE-108a subprocess remediation and GE-108c tuple fix (both completed in PR #104).

## Risk & Safety

- Touches money? No.
- Touches data? No.
- Reversibility? Guard changes are reversible by reverting the template files and
  rebuilding. Any handler edits are additive/behavior-preserving.
- If option 1 (honor noqa) is chosen, ensure the noqa parsing cannot be abused to
  blanket-suppress — scope it to the specific violation code on the specific line,
  matching Ruff semantics.
