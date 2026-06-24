---
title: "Add gh account pre-flight (EMU switch + verify, REST fallback) to finalize-feature.js"
status: todo
components:
  - git_vcs_operations
  - build_pipeline
created: 2026-06-24
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
files_touched:
  - templates/workflows-js/finalize-feature.js
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: not_needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
---

# 05: Add gh account pre-flight to finalize-feature.js

## Actor / Goal

In order to stop finalize from stalling or failing at PR open/merge under an
Enterprise Managed User (EMU) `gh` account, we need a pre-flight that selects and
verifies the correct `gh` account before any `gh` operation, with a REST-API
fallback when `gh pr create`/`merge` is EMU-blocked.

## Context

Every `gh` call in `finalize-feature.js` (PR probe, PR open via the pull-request
agent, `gh pr view`, `gh pr merge`) assumes the active `gh` account can operate on
the repo. But the default-active account in this environment is the EMU
`henzeh_roche`, which silently blocks the GraphQL `createPullRequest`/merge
mutations. The CLAUDE.md "EMU account" section and user-memory both document the
workaround: `gh auth switch --user urlmonitor` → verify with `gh auth status` →
fall back to `gh api -X POST repos/<org>/<repo>/pulls ...` on the EMU error. The
JS workflow currently encodes none of this, so a finalize run under the wrong
account fails at Step 1 or Step 4.

The account name and org/repo should be config-driven (not hard-coded), e.g. read
from a settings/config value, so the pre-flight is portable to other installs.

## Acceptance Criteria

- [ ] AC-1: Before any `gh` operation, finalize runs a `gh auth status` probe and,
  when a configured target account is set and not active, runs
  `gh auth switch --user <account>` then re-verifies with `gh auth status`.
- [ ] AC-2: If the configured account cannot be activated, finalize halts with a
  clear, actionable message (which account is needed, how to log in) rather than
  proceeding and failing opaquely mid-merge.
- [ ] AC-3: When `gh pr create` / `gh pr merge` returns the EMU
  `createPullRequest`-blocked error, finalize falls back to the REST endpoint
  (`gh api -X POST repos/<org>/<repo>/pulls` for create; the REST merge endpoint
  for merge) and continues.
- [ ] AC-4: The target account and org/repo are read from config (not hard-coded),
  with a documented default; on installs with no EMU constraint the pre-flight is
  a no-op.

## AC Coverage

| AC | Test | Implementation | Validated |
|----|------|----------------|-----------|
| AC-1 | | | |
| AC-2 | | | |
| AC-3 | | | |
| AC-4 | | | |

## Comments

## Implementation Tasks
- [ ] Add a `gh` pre-flight step (status → switch → verify) before Step 1.
- [ ] Add EMU-error detection + REST fallback around PR create/merge.
- [ ] Source account/org/repo from config with a sane default + no-op path.
- [ ] Tests for: account-switch path, halt-on-failure, EMU REST fallback, no-op path.

## Risk & Safety
- Touches money? No.
- Touches data? No — auth/PR plumbing only.
- Reversibility? High.
