---
title: "Glossary coverage hook: hook mode reports new terms instead of blacklisting them"
date: "2026-10-06"
time: "04:54"
type: manual
components: 
  - glossary
  - commit_guardian
summary: "The pre-commit glossary check no longer silently puts every new term on the blacklist; it lists new terms and points to the triage flow instead."
description: "In hook mode the glossary coverage check could not ask the triage agent, so it fell back to a placeholder that put every candidate term on the blacklist and re-staged the glossary files. An open known issue (the detector path is unreachable) hid this; fixing that issue alone would have started it. Hook mode is now report-only: it writes nothing, lists the new terms with a pointer to the triage flow, and exits successfully. A real triage function, when injected, still applies its decisions. The CLAUDE.md wording now matches, and one false positive on the new history line is allowlisted."
tickets: 
  - TICKET-20261002-GlossaryHookStubBlacklistsNewTerms
---

## Entry

### Changed

- `templates/scripts/commit_guardian/check_glossary_coverage.py` — hook mode is report-only.
- `CLAUDE.md`, `.claude/CLAUDE.md` — glossary hook description matches the behaviour.
- `.security-allowlist` — one ENTROPY_HIGH false positive on the new history line.

### Added

- `unit_tests/commit_guardian/test_check_glossary_coverage_hook_mode.py`.
