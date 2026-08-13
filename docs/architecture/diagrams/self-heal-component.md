---
title: "Self-Healing Config Hook — Component Diagram"
description: "L3 component diagram of ensure_precommit_config.py: its git-commondir dependency, its symlink-or-copy outputs, its index-0 manifest registration, and the gates that consume it."
type: architecture
diagram_type: component
status: active
flight_level: L3-Component
created: 2026-07-06
last_updated: 2026-07-06
parent: docs/architecture/components/worktree-quality-gate-guard.md
components:
  - commit_guardian
related_docs:
  - docs/architecture/components/worktree-quality-gate-guard.md
  - docs/architecture/diagrams/self-heal-sequence.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
related_adrs:
  - ADR-031
tags:
  - self-healing
  - index-0
  - symlink
  - fallback-copy
---

# Self-Healing Config Hook — Component Diagram

This diagram shows `ensure_precommit_config.py` as a component: its resolver
dependency, the two re-materialisation outputs it can produce, its index-0
registration in the manifest, and the gates that consume it.

---

```mermaid
flowchart TB
    classDef core fill:#d1fae5,stroke:#059669,stroke-width:2px,font-weight:bold;
    classDef dep fill:#dbeafe,stroke:#2563eb,stroke-width:2px;
    classDef out fill:#fef9c3,stroke:#ca8a04,stroke-width:2px;
    classDef reg fill:#ede9fe,stroke:#7c3aed,stroke-width:2px;
    classDef consumer fill:#ffedd5,stroke:#ea580c,stroke-width:2px;

    subgraph GUARD ["Worktree Quality Gate Guard"]
        CORE["ensure_precommit_config.py\nensure_config(worktree_root)\nindex 0 · fail-closed · idempotent"]:::core
        RESOLVER["_find_main_tree_root\n→ _resolve_git_commondir\n(git commondir resolver)\nfallback: _PACKAGE_ROOT"]:::dep
        OUT_SYM[".leafcutter symlink\n(preferred, POSIX)"]:::out
        OUT_COPY[".pre-commit-config.yaml copy\n(_atomic_copy, NTFS/WSL fallback)"]:::out
    end

    REG["commit_guardian.json\nhooks_manifest.hooks[0]\nid: ensure-precommit-config\nalways_run · stages:[pre-commit]"]:::reg

    subgraph GATES ["Consuming gates"]
        G1["setup_ticket_worktree.py\n(create-time)"]:::consumer
        G2["building-epics SKILL §2.0\n(pre-drive)"]:::consumer
        G3["commit.md template\n(commit-phase)"]:::consumer
    end

    CORE -->|"resolve main tree root"| RESOLVER
    CORE -->|"1. try os.symlink"| OUT_SYM
    CORE -->|"2. on OSError, copy"| OUT_COPY
    REG -.->|"registers + runs first"| CORE
    G1 -.->|"invokes as remedy"| CORE
    G2 -.->|"invokes as remedy"| CORE
    G3 -.->|"invokes as remedy"| CORE
```

Parent: [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md)

---

## Elements

| Element | Role |
|---|---|
| `ensure_config(worktree_root)` | Core entry point. Idempotent no-op when config already resolves; otherwise re-materialises it; fail-closed (returns `False`, never raises). |
| `_resolve_git_commondir` (via `_find_main_tree_root`) | Resolves the shared `.git` commondir to locate the main tree's `.leafcutter`. Falls back to `_PACKAGE_ROOT` when git resolution is unavailable. |
| `.leafcutter` symlink | Preferred output — a symlink to the main tree's `.leafcutter` directory, preserving all hook configs. |
| `.pre-commit-config.yaml` copy | Fallback output — an atomic write-temp-then-rename copy used when symlink creation raises `OSError` (e.g. NTFS/WSL). |
| `commit_guardian.json` `hooks[0]` | Registers the hook at index 0 (`always_run`, `stages: [pre-commit]`) so it runs before every other hook. |
| Consuming gates | `setup_ticket_worktree.py`, building-epics SKILL §2.0, and `commit.md` invoke this hook as the remedy when the probe fails. |

## Cross-References

- [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md) — parent container.
- [Self-Heal Sequence](self-heal-sequence.md) — the runtime flow of this component on every commit.
- [ADR-031 — Worktree Quality Gate Guard](../adrs/ADR-031-worktree-quality-gate-guard.md).

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [architecture-diagram-author, EPIC-WorktreeQualityGateGuard/08]:
  Initial creation (BO-1700c-2). Component view of ensure_precommit_config.py
  rendered as a flowchart (diagram_type: component): resolver dependency,
  symlink/copy outputs, index-0 registration, and the three consuming gates.
====================================================================
-->
