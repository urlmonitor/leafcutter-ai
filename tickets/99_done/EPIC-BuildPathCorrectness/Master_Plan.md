---
title: "EPIC: Build Path Correctness — config-driven output paths and hook integrity"
type: epic
status: done
components:
  - build_pipeline
created: 2026-06-04
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
---

# EPIC: Build Path Correctness

## Goal

Ensure that all build phases deploy artifacts to config-driven paths (not
hardcoded) and that every hook registered in `commit_guardian.json` has a
corresponding script at the canonical template path. Prevent recurrence via
a build-time referential integrity check.

## Context

During self-hosting builds (`build-self.sh`), several outputs landed at the
workspace root (`leafcutter/`) instead of the git root (`leafcutter-ai/`)
because build phases hardcoded paths instead of reading `docs_root` or
`git_root` from config. Separately, 7 hook scripts were registered in the
manifest but existed only at the deprecated `templates/commit-guardian/` path
— the build reads from `templates/scripts/commit_guardian/` since
EPIC-PortableInstallHardening (2026-06-02).

Both classes of bug share a root cause: **build outputs are not validated
against the config or the manifest before being deployed.**

## Sub-Tickets

| # | File | Description | Depends on | Status |
|---|------|-------------|------------|--------|
| 01 | [01_fix_docs_root_git_root.md](./01_fix_docs_root_git_root.md) | Fix 4 build phases to use config.get("docs_root") and config.get("git_root") | — | done |
| 02 | [02_hook_integrity_check.md](./02_hook_integrity_check.md) | Build-time hook referential integrity check + fix check_contract_shrinking false-positive | 01 | todo |

## Execution Order

Ticket 01 is already done (fix merged + git_root shim in working diff).
Ticket 02 can proceed immediately — it adds the structural guard that
prevents the class of bug from recurring.

## Cross-Epic Dependencies

- **EPIC-UnifyACPipeline** depends on this epic's ticket 02 being complete
  (hooks must work correctly before the v2 pipeline can be tested end-to-end).

## Risk & Safety

- Touches money? No.
- Touches data? No — build output paths and hook infrastructure only.
- Reversibility? All config keys have defaults matching pre-fix behaviour.
  Consumer projects with no `docs_root` or `git_root` override are unaffected.
