---
title: "Known Issues Register"
description: "Index of open, reproducible defects in this package that are not yet fixed, organised by component. Each entry states severity, how to detect the issue, any workaround, and a suggested fix."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - infrastructure
related_docs:
  - docs/pre-commit-hooks.md
  - docs/build-pipeline.md
  - docs/architecture/agent_delivery_workflows.md
---

# Known Issues Register

Open, reproducible defects in this package, organised by component. One file per
component; each entry carries a stable `KI-<COMPONENT>-<n>` id.

This register exists because a defect found and then only mentioned in a commit
message is, in practice, lost. Several issues below are of a kind the package is
explicitly built to prevent — a gate that never runs, a check that silently
skips, a driver that commits past its own blockers — so leaving them
undocumented would be self-defeating.

## What belongs here

An entry should be **open**, **reproducible**, and **observed** rather than
suspected. Each states:

- **Severity** and why
- **Detection** — how to tell it is happening, which for silent-failure defects
  is the load-bearing part
- **Workaround**, if any
- **Suggested fix**

Fixed issues are removed, not marked resolved — git history is the record. The
one exception is a short "fixed, recorded for context" section where knowing an
issue *used to* exist explains present code.

## Index

| Component | File | Open entries |
|---|---|---|
| `supervisor_system` | [supervisor-system.md](supervisor-system.md) | 3 |
| `commit_guardian`, `precommit_hooks` | [commit-guardian.md](commit-guardian.md) | 4 |
| `testing_quality` | [testing-quality.md](testing-quality.md) | 1 |
| `build_orchestration`, `doc_compliance` | [build-orchestration.md](build-orchestration.md) | 2 |

## Highest severity first

- **KI-SUP-1** — `/build-feature`'s commit phase runs while gates are recorded
  `failed`. Phantom-done at the orchestration layer.
- **KI-TQ-1** — bare-name `sys.modules` caching lets a stale deployed copy shadow
  the canonical module for a whole pytest session. Can hide a real fix *or* a
  real bug.
- **KI-CG-1** — `check-predone-scope` blocks any lifecycle-repair commit and
  reconciles branch-wide, so no commit boundary satisfies it.
- **KI-CG-2** — `check_ticket_signoff_parity.py` silently skips check #6 on a
  wrong registry path, then exits 0.

## Provenance

All current entries were found on 2026-08-19 during
`EPIC-GE122UniquenessPassAndRepair`, and every one was observed directly — by
running the code, reading a hook's stderr, or watching a drive behave — not
inferred from reading source.
