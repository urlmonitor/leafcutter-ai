---
title: "Glossary coverage hook: in hook mode every new term would be blacklisted by the standalone stub"
status: todo
components:
  - glossary
  - commit_guardian
created: 2026-10-02
depends_on: []
priority: medium
requires_diagram: false
requires_adr: false
change_target: code
risk_surface: internal
tags:
  - glossary
  - pre-commit
  - latent-defect
last_updated: 2026-10-02
agents:
  test-writer: signed_off
  python-coder: signed_off
  commit: signed_off
---

# Glossary coverage hook: in hook mode every new term would be blacklisted by the standalone stub

## Actor / Goal
In order to keep `docs/glossary_blacklist.md` meaningful, we need the `check-glossary-coverage`
pre-commit hook to never blacklist a term it has not really triaged.

## Context
- `templates/scripts/commit_guardian/check_glossary_coverage.py` `main()` calls
  `check_glossary_coverage(repo_root)` without a `dispatch_fn`. Its fallback is
  `_dispatch_triage_standalone`, which by its own docstring is meant for "unit tests and
  standalone runs". It answers `add_to_blacklist` ("standalone-mode placeholder") for every
  candidate. The hook then applies those decisions and re-stages the glossary files.
- A git hook cannot dispatch the `glossary-triage` agent, so this is the path every real commit
  takes.
- **No stub rows exist in the blacklist today.** The detector is unreachable from the hook (open
  known issue
  `docs/known-issues/commit-guardian/open-high-ki-cg-20260831-glossary-coverage-detector-path-unreachable.md`),
  so the hook finds nothing.
- **The two defects mask each other.** Fixing that known issue alone would start silently
  blacklisting every new term on every commit.
- **Seen 2026-10-02:** correct glossary coverage needed manual triage before commit (detector,
  then `glossary-triage` agents, then `glossary_bootstrap.py --apply-decisions`).

## Scope
- In hook mode, never write stub decisions. Report the novel terms instead: warn and exit 0
  (fail-open), or write them to a pending-triage list. Choose and record which.
- Make sure the CLAUDE.md promise ("dispatches the glossary-triage agent automatically") matches
  reality, or correct the text.
- Fix together with, or before, the known issue above.

## Design Decision (2026-10-02)
Of the two options in Scope, take the simpler one. In hook mode (no `dispatch_fn`), the hook
writes NOTHING to `docs/glossary.md` or `docs/glossary_blacklist.md`. It prints the novel terms
with a pointer to the triage flow (`glossary-triage` agents plus
`glossary_bootstrap.py --apply-decisions`) and exits 0 (fail-open, unchanged). The stub stays
available for unit tests only. An injected real `dispatch_fn` (agent context) still applies its
decisions as today.

## Out of Scope
- The triage agent's classification quality.
- The known issue's detector-path fix itself (separate).

## Test Requirements

```yaml
tests:
  - name: test_hook_mode_writes_no_stub_decisions
    location: unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py
    type: unit
    covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
    description: |
      In a temporary git repo with a staged .md file containing a novel jargon term, run the
      hook the way pre-commit does (main(), no dispatch_fn). Assert that docs/glossary.md and
      docs/glossary_blacklist.md are byte-identical before and after, that nothing new is
      staged, and that the exit code is 0. This fails today: the stub blacklists the term.

  - name: test_hook_mode_reports_novel_terms
    location: unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py
    type: unit
    covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
    description: |
      Same setup. Assert the hook's output names the novel term and points to the triage flow
      (glossary-triage / glossary_bootstrap.py --apply-decisions), so nothing is lost silently.

  - name: test_injected_dispatch_still_applies_decisions
    location: unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py
    type: unit
    covers: TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
    description: |
      With an injected dispatch_fn test double that returns add_to_glossary for the term,
      check_glossary_coverage() applies the decision to docs/glossary.md as today, so the
      agent-context path is preserved.
```

## Comments

### 2026-10-02 14:30 — test-writer (status: ok)
feedback-id: fb_2026-10-02_14a082a8
completion_manifest:
  tests_written: true
  red_baseline_verified: true
  cross_layer_seam_answer:
    result: covered
    producing_side: "check_glossary_coverage.main() (hook entry, no dispatch_fn)"
    consuming_side: "real glossary_detector.detect_candidates output and real git index in a temp repo"
  reachability_entry_point_answer:
    result: resolved
    entry_point: "check_glossary_coverage.main() with real cwd git repo (pre-commit entry)"
Wrote unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py (3 tests).
red_baseline:
  - test_name: test_hook_mode_writes_no_stub_decisions
    file: unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py
    error: "AssertionError: blacklist bytes differ; '| backfill_complete | standalone-mode pla...' row appended"
  - test_name: test_hook_mode_reports_novel_terms
    file: unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py
    error: "AssertionError: 'backfill_complete' not found in 'check-glossary-coverage: 1 novel jargon candidate(s) detected.\n'"
Note: test_injected_dispatch_still_applies_decisions passes today by design (preservation guard for the agent path). The detector is patched in via _load_detector because of the open detector-path known issue.

### 2026-10-02 15:05 — python-coder (status: ok)
feedback-id: (submit-failed)
Hook mode (no dispatch_fn) is now report-only in check_glossary_coverage.py (_report_novel_terms); nothing written or staged, exit 0. Stub kept for tests. CLAUDE.md and .claude/CLAUDE.md text corrected.
red_baseline_results:
  - test_name: test_hook_mode_writes_no_stub_decisions
    result: green
  - test_name: test_hook_mode_reports_novel_terms
    result: green

### 2026-10-06 04:57 — commit (status: ok)
feedback-id: fb_2026-10-06_327c5ab7
completion_manifest:
  pre_commit_hooks_pass: true
  commit_message_valid: true
  ticket_staged: true
Auto-authorized commit gate: subject "fix(glossary): hook mode reports novel terms instead of stub-blacklisting them"; staged files: .claude/CLAUDE.md, CLAUDE.md, templates/scripts/commit_guardian/check_glossary_coverage.py, tickets/00_inbox/TICKET-20261002-GlossaryHookStubBlacklistsNewTerms.md, unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py.
