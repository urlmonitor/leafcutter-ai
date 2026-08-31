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

Counts recounted 2026-08-31. This table had listed five of the thirteen files and was stale
by roughly an order of magnitude on the two largest — an index nobody can trust is worse than
no index, since it reads as "there are five commit-guardian issues" when there are 35.

| Component | File | Open entries |
|---|---|---|
| `commit_guardian`, `precommit_hooks` | [commit-guardian.md](commit-guardian.md) | 39 |
| `build_orchestration`, `doc_compliance` | [build-orchestration.md](build-orchestration.md) | 30 |
| `build_pipeline` | [build-pipeline.md](build-pipeline.md) | 26 |
| `ac_driven_dev` | [ac-driven-dev.md](ac-driven-dev.md) | 23 |
| `ac_store` | [ac-store.md](ac-store.md) | 15 |
| `knowledge_management` | [knowledge-management.md](knowledge-management.md) | 12 |
| `testing_quality` | [testing-quality.md](testing-quality.md) | 11 |
| `supervisor_system` | [supervisor-system.md](supervisor-system.md) | 6 |
| `agent_registry` | [agent-registry.md](agent-registry.md) | 3 |
| `documentation_system` | [documentation-system.md](documentation-system.md) | 3 |
| `feedback_collector` | [feedback-collector.md](feedback-collector.md) | 3 |
| `changelog` | [changelog.md](changelog.md) | 2 |
| `security_scanner` | [security-scanner.md](security-scanner.md) | 1 |
| | **total** | **174** |

Two id conventions are in use — `KI-CG-035` and `KI-CG-20260826-1612`. A count that
matches only the first undercounts; the date form is the newer of the two and is the
one that cannot collide.

**Known id collision, unrepaired:** `commit-guardian.md` carries **two** distinct entries
numbered `KI-CG-012` — one on hook test seams, one on `check-ac-schema` failing open on an
empty staged set. Both are cited elsewhere by that id, so neither can be silently renumbered
without breaking references; repairing it means choosing which keeps the number and updating
every citation to the other.

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
- **KI-TQ-2** — the exit gate's tree-purity guard false-positives on any
  concurrent write, producing failures indistinguishable from real ones.
- **KI-FC-1** — `ac-validator` is missing from every category's
  `allowed_writers`, so it has never once submitted feedback.

## The common shape

Nine of the twelve entries are the same defect class: **a check that reports
success while seeing less than it should**. A hook that skips one of its own
checks and exits 0. A gate registered nowhere. A driver that commits past its own
blockers. An agent that cannot write to the corpus it is supposed to feed. An
oracle that shares the bug it exists to detect.

None of these is visible in a passing test run — the suite was green for every
one of them. That is worth stating plainly in a package whose purpose is to
detect exactly this: **green tests are not evidence against this failure class,
because this failure class is what green looks like when the check is blind.**

What did find them: measuring instead of asserting; probing with synthetic
inputs a real-artifact sweep cannot reach; deliberately breaking the
implementation to confirm the tests notice; and agents refusing to improvise past
their own algorithm's limits rather than producing a convenient pass.

## Provenance

All current entries were found on 2026-08-19 during
`EPIC-GE122UniquenessPassAndRepair`, and every one was observed directly — by
running the code, reading a hook's stderr, or watching a drive behave — not
inferred from reading source.
