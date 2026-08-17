---
title: "Worktree Quality Gate Guard — Container Overview"
description: "Container-level overview of the worktree quality-gate guard subsystem: the four-check probe, the index-0 self-healing config hook, and the three lifecycle gates that keep pre-commit hooks firing inside git worktrees."
type: architecture
status: active
flight_level: L2-Container
created: 2026-07-06
last_updated: 2026-07-06
components:
  - commit_guardian
children:
  - docs/architecture/diagrams/probe-sequence.md
  - docs/architecture/diagrams/self-heal-component.md
  - docs/architecture/diagrams/self-heal-sequence.md
  - docs/architecture/diagrams/gates-sequence.md
related_docs:
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
  - docs/architecture/components/commit-guardian.md
related_adrs:
  - ADR-031
tags:
  - worktree
  - pre-commit
  - quality-gate
  - fail-closed
  - self-healing
---

# Worktree Quality Gate Guard — Container Overview

The **Worktree Quality Gate Guard** is a subsystem of the [Commit Guardian](commit-guardian.md)
that defends against the *silent-skip* failure mode: a fresh git worktree
created from `origin/main` inherits neither the `.leafcutter` symlink nor a
populated `.pre-commit-config.yaml`, so `git commit` runs with
`PRE_COMMIT_ALLOW_NO_CONFIG=1` and **every** package hook is silently skipped.
Code lands unchecked while every commit still reports success.

This container groups three cooperating parts, each documented by a child
diagram at the component level (L3):

| Part | Script | Responsibility | Child diagram |
|---|---|---|---|
| Four-check probe | `verify_precommit_active.py` | Prove the hook chain will actually *fire* (not just that files are present). | [Probe Sequence](../diagrams/probe-sequence.md) |
| Self-healing hook (structure) | `ensure_precommit_config.py` | Re-materialise the config in a worktree; registered at manifest index 0. | [Self-Heal Component](../diagrams/self-heal-component.md) |
| Self-healing hook (runtime) | `ensure_precommit_config.py` | Runtime flow on every commit: symlink, else atomic copy, else fail-closed. | [Self-Heal Sequence](../diagrams/self-heal-sequence.md) |
| Lifecycle gates | `setup_ticket_worktree.py`, building-epics SKILL §2.0, `commit.md` | Invoke the probe at three points and halt on failure. | [Gates Sequence](../diagrams/gates-sequence.md) |

## Key invariants

1. **Fail-closed, no fail-open path.** Any check that raises (including a canary
   subprocess timeout) is recorded as `False` and its key is appended to
   `failing_checks`; the probe exits non-zero.
2. **Execution proof via canary (Check D).** The canary check requires the hook
   chain to run `precommit_canary.py` and emit `PRECOMMIT_CANARY_OK` — presence
   of a config file alone is never accepted as proof.
3. **Self-heal runs first.** `ensure-precommit-config` is registered at
   `hooks_manifest.hooks[0]` so it repairs the config before any other hook runs.

## Cross-References

- [ADR-031 — Worktree Quality Gate Guard](../adrs/ADR-031-worktree-quality-gate-guard.md)
  — the design decision this subsystem implements.
- [Commit Guardian](commit-guardian.md) — the parent pre-commit enforcement layer.

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [architecture-diagram-author, EPIC-WorktreeQualityGateGuard/08]:
  Created as the L2-Container parent for the four worktree quality-gate guard
  diagrams (BO-1700a-11, BO-1700c-2, BO-1700c-3, BO-1700d-4). Introduced so the
  L3 component/sequence diagrams have a strictly-higher-level parent that
  satisfies the check-mermaid-parent-link bidirectional rule; commit-guardian.md
  is itself L3-Component and therefore not eligible as their parent.
====================================================================
-->
