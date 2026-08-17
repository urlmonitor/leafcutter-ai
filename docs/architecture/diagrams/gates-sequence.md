---
title: "Lifecycle Gates — Probe Invocation Sequence"
description: "L3 sequence diagram of the three worktree lifecycle gates (create-time, pre-drive, commit-phase) invoking verify_precommit_active.py and halting the flow on probe failure."
type: architecture
diagram_type: sequence
status: active
flight_level: L3-Component
created: 2026-07-06
last_updated: 2026-07-06
parent: docs/architecture/components/worktree-quality-gate-guard.md
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/worktree-quality-gate-guard.md
  - docs/architecture/diagrams/probe-sequence.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
related_adrs:
  - ADR-031
tags:
  - gates
  - create-time
  - pre-drive
  - commit-phase
---

# Lifecycle Gates — Probe Invocation Sequence

This diagram shows the three points across the worktree lifecycle where a gate
invokes the probe `verify_precommit_active.py`. Each gate proceeds only when the
probe exits `0`; on a non-zero exit it surfaces the `failing_checks` to the user
and halts.

> **Same probe, three call sites.** Create-time, pre-drive, and commit-phase all
> run the identical four-check probe. A failure at any gate offers the user the
> same options: fix (run `ensure_precommit_config.py`), retry, or override with
> explicit authorisation.

---

```mermaid
sequenceDiagram
    autonumber
    actor User
    participant Setup as setup_ticket_worktree.py
    participant Skill as building-epics SKILL §2.0
    participant Commit as commit.md template
    participant Probe as verify_precommit_active.py
    participant Heal as ensure_precommit_config.py

    Note over Setup,Probe: Gate 1 — create-time
    Setup->>Probe: verify_precommit_active(<worktree-root>)
    alt exit 0 (all checks pass)
        Probe-->>Setup: proceed — worktree is protected
    else exit 1 (failing_checks)
        Probe-->>User: surface failing_checks — halt
        User->>Heal: fix (run ensure_precommit_config.py)
        User->>Setup: retry / or override with explicit auth
    end

    Note over Skill,Probe: Gate 2 — pre-drive (before first phase agent)
    Skill->>Probe: verify_precommit_active(<worktree-root>)
    alt exit 0
        Probe-->>Skill: proceed — spawn first phase agent
    else exit 1
        Probe-->>User: surface failing_checks — halt drive
        User->>Heal: fix
        User->>Skill: retry / or override with explicit auth
    end

    Note over Commit,Probe: Gate 3 — commit-phase (before staging)
    Commit->>Probe: verify_precommit_active(<worktree-root>)
    alt exit 0
        Probe-->>Commit: proceed — stage and commit
    else exit 1
        Probe-->>User: surface failing_checks — halt commit
        User->>Heal: fix
        User->>Commit: retry / or override with explicit auth
    end
```

Parent: [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md)

---

## The three gates

| Gate | Call site | When it runs | On failure |
|---|---|---|---|
| Create-time | `setup_ticket_worktree.py` | Immediately after the worktree is created. | Surface `failing_checks`; user fixes, retries, or overrides. |
| Pre-drive | building-epics SKILL §2.0 | Before the first phase agent is spawned. | Halt the drive; user fixes, retries, or overrides. |
| Commit-phase | `commit.md` template | Before staging files for a commit. | Halt the commit; user fixes, retries, or overrides. |

## User options on failure

1. **Fix** — run `ensure_precommit_config.py` to re-materialise the config, then re-run the probe.
2. **Retry** — re-invoke the gate once the environment is repaired.
3. **Override** — proceed only with explicit authorisation (the fail-closed default is to halt).

## Cross-References

- [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md) — parent container.
- [Probe Sequence](probe-sequence.md) — the four-check probe each gate invokes.
- [Self-Heal Sequence](self-heal-sequence.md) — the remedy the "fix" option triggers.
- [ADR-031 — Worktree Quality Gate Guard](../adrs/ADR-031-worktree-quality-gate-guard.md).

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [architecture-diagram-author, EPIC-WorktreeQualityGateGuard/08]:
  Initial creation (BO-1700d-4). Sequence of the three lifecycle gates
  (create-time, pre-drive, commit-phase) invoking verify_precommit_active.py,
  with the fix/retry/override options on a fail-closed halt.
====================================================================
-->
