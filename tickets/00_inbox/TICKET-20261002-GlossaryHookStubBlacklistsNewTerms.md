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
  python-coder: needed
  commit: needed
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

## Out of Scope
- The triage agent's classification quality.

## Comments
