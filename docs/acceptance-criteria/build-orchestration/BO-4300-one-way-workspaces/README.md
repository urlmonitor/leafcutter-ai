---
title: BO-4300 — One-Way Workspaces
type: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
- worktree_manager
- build_orchestration
description: Overview of BO-4300 — One-Way Workspaces.
---
# BO-4300 — One-Way Workspaces

## Purpose

This directory holds the acceptance-criteria (AC) store records for the
`BO-4300` cluster: "Every piece of separate work gets its workspace one
dependable way." The cluster's shared goal is that whenever automation, or a
person, needs a separate place to work (a ticket, a feature, an AC-authoring
session, an epic, a fast-lane fix, or a scratch session), there is exactly one
way to get it — the same result, from anywhere, every time — and the workspace
is either fully ready (its own line of work, started from the latest shared
main, with its protections switched on) or the caller is told plainly why not.
`BO-4300a-1` (this cluster's first delivered record) implements the one
workspace maker every route now goes through.

## Key Files

- `BO-4300.yaml` — the L0 parent record for the whole cluster.
- `BO-4300a-1.yaml` — "Every route that asks gets the same kind of workspace
  from the same maker": the one maker's CLI (`ensure`/`locate`/`list`/
  `verify`/`remove`/`where`) and its separate, uncached project-root resolver
  module. Delivered by `templates/scripts/worktree.py`,
  `templates/scripts/worktree_git.py`, `templates/scripts/worktree_admin.py`
  and `templates/scripts/workspace_root.py` (deployed to
  `<install-root>/scripts/` by named entries in
  `scripts/build_phases_script_deploy_standalone.py` and
  `scripts/build_deploy_manifest_helpers.py`).
- `BO-4300a-1-i.yaml`, `-ia.yaml`, `-ib.yaml`, `-ii.yaml` — child records for
  the same maker (workspace skill wiring, ticket-location resolution inside a
  workspace).
- `BO-4300a-2.yaml` through `BO-4300f-4-i.yaml` — the remaining `BO-4300`
  child records: work-identity normalisation, project-root resolution order
  (`BO-4300b-1`), the maker's result contract (`BO-4300c-2`), per-stage hook
  declarations, resume/idempotency behaviour, and retirement of the legacy
  `setup_ticket_worktree.py` script (`BO-4300f-2`).

## Critical Context

- **One maker, one resolver.** Per `BO-4300a-1`'s Implementation Notes, no
  other code path in the package may create, clone, locate or remove a
  workspace once `BO-4300f-2` retires `setup_ticket_worktree.py`. The project-
  root resolver lives in its own module and must not reuse
  `templates/scripts/commit_guardian/_resolve_root.py` (KI-CG-20260925).
- **Result-contract dependency.** `BO-4300a-1`'s own `Expects From` clause
  names `BO-4300c-2` as the governing shape for every answer the maker emits
  (status/code enums, exit codes, common fields). Records in this directory
  that reference "the answer contract" mean `BO-4300c-2.yaml` specifically.
- **Deferred scope, not silently dropped.** Several records here explicitly
  defer sub-scope to a sibling record rather than pre-empting it — e.g. the
  resolver module's full `how` resolution order (`workspace-marker`/
  `child-search`/`sibling-search`) is `BO-4300b-1`'s own `it_requirements`,
  and the per-stage `checks` dict rename is `BO-4300c-1-ii`'s. Do not
  implement a deferred sibling's scope from within another record's ticket —
  it duplicates ownership and risks disagreeing with that record's own design
  once it lands.

## Maintenance

- Add new child records here with the same `BO-4300<letter>-<n>` naming
  convention already in use; keep `depends_on` accurate so
  `scripts/ac_store/ac_coverage_resolver.py` can trace fulfillment correctly.
- When a record's own `files_touched`/`implementation_files` change, keep this
  README's "Key Files" list in sync so it stays a usable map of the cluster,
  not a stale snapshot.
- This README exists to satisfy the package's per-directory documentation
  requirement (`.agents/rules/documentation.md` #2) the first time a file in
  this directory was staged after that rule started being enforced here; it
  was not previously required across the wider `docs/acceptance-criteria/`
  tree, so sibling `BO-*` directories may still lack one.
