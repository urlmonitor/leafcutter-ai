---
advances_current_outcome: true
agents:
  commit: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  pull-request: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  test-writer: needed
components:
- build-pipeline
created: '2026-06-29'
depends_on:
- BP-1200a-1-ii
files_touched:
- templates/scripts/commit_guardian/
- templates/scripts/doc_compliance/
- scripts/build.py
- scripts/build_phases.py
- unit_tests/test_build_guard_real_package.py
priority: high
requires_adr: false
requires_diagram: false
roadmap_phase: phase_1
source_ac: BP-1200a-1
status: todo
title: Restore remaining #164-untracked package scripts for fresh-clone-green test suite
---

# Restore remaining #164-untracked package scripts for fresh-clone-green test suite

## Actor / Goal

As the leafcutter-ai maintainer, I want the full test suite to pass on a fresh
clone (AC `BP-1200a-1`), so that CI's "Test suite (pytest)" job is green on
`main` and consumer installs are reliable.

## Context

This is the follow-up to `TICKET-20260629-BP-1200a-1-ii` (merged in PR #180),
which fixed the **build-guard** half of the problem: PR #164 (commit
`83737a44`) untracked ~90 package files under `scripts/commit_guardian/`
(incl. `hooks/`), `scripts/doc_compliance/`, `scripts/feedback/`, and
`scripts/sync_platforms/`, converting them to gitignored shim build-outputs
with no tracked source. PR #180 restored `templates/scripts/feedback/` (7
files) plus `known_failing_tests.py`, `transform_decision_history.py`, and
`check_test_fixture_bloat.py`, so `python scripts/build.py --target-dir .` now
exits 0 and pytest **collection** is clean.

**Remaining problem:** with `pytest -x`, CI now fails at the next layer — tests
that *run* but fail because a build-generated dependency is still missing. First
observed: `tests/commit_guardian/test_check_ac_done_on_merge.py` →
`scripts/commit_guardian/hooks/check_ac_done_on_merge.py` does not exist. More
of the ~90 untracked files are needed by tests but have no tracked
`templates/scripts/...` source yet.

## Approach

1. On a fresh build (`build.py --target-dir /tmp/<fresh>`), run the FULL suite
   (`pytest tests/ unit_tests/ -q`, no `-x`) and enumerate **every** failure
   whose cause is a missing build-generated module/file.
2. For each, recover the canonical source from git history
   (`git show 83737a44^:<path>`) and place it in the correct **tracked**
   package-source location (`templates/scripts/commit_guardian/`,
   `templates/scripts/commit_guardian/hooks/`, `templates/scripts/doc_compliance/`,
   etc.), wiring `build_phases.py` / the `build.py` manifest as needed.
3. **Distinguish accidental vs intentional removals**: some of the ~90 files may
   have been deliberately superseded by #164. Only restore what a current test
   actually requires; for any that look intentionally removed, leave the obsolete
   test rather than resurrecting dead code, and note the decision.
4. Respect the ADR-001/ADR-004 self-hosting boundary (tracked source in the
   package source tree; never commit build OUTPUTS into `scripts/`). Cross-ref
   ADR-016.
5. Strengthen `unit_tests/test_build_guard_real_package.py` to assert a full
   fresh-clone run (not just `--collect-only`) is green.

## Acceptance Criteria

```gherkin
Given a brand-new checkout with locally-generated build outputs absent,
When `python scripts/build.py --target-dir .` is run and then
  `python -m pytest tests/ unit_tests/ -q` is run,
Then the suite reports zero errors and zero failures caused by a missing
  build-generated module or file,
And any remaining failures (if accepted) are genuine, pre-existing, and
  explicitly documented as out of scope for this ticket.
```

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Comments
