---
title: "Changelog ac-authoring/ci-ac-gate (uncommitted) — Add blocking AC store validation CI job — 2026-08-14"
date: "2026-08-14"
time: "07:22"
type: manual
components: 
  - ac_store
  - precommit_hooks
summary: "Added a required CI check that blocks a pull request from merging a structurally invalid acceptance-criteria record, closing a gap where nothing in continuous integration validated the acceptance-criteria store."
description: "Category: Features. Adds a new blocking job \"AC store valid\" (ac-store-valid) to .github/workflows/ci.yml, running only on pull_request events, alongside the existing ruff, component vocab, pytest, proof-of-done, changelog-presence, and informational-mypy jobs (none of which read docs/acceptance-criteria/). The job runs git reset --soft onto the base ref so the PR's added/modified files appear staged, then invokes the same six pre-commit hooks used locally (check-ac-schema, check-ac-tree-limits, check-ac-governance, check-ac-parent-covered-by, check-ac-circular-deps, check-ac-pattern-refs) via pre-commit so merge-time and commit-time rules cannot drift; without the reset the fail-open hooks would validate nothing against a clean index. Scoped to the PR diff only, not the whole store, because the store currently has 57 orphaned children; a whole-store gate on main is specified as ACS-200h but deliberately not implemented yet. Change is currently uncommitted in worktree ac-authoring/ci-ac-gate."
acs: 
  - ACS-200g
  - ACS-200g-1
  - ACS-200g-2
  - ACS-200h
  - ACS-200i
---

## Entry
