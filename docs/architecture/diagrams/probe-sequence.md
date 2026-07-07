---
title: "Probe Execution — Four-Check Sequence"
description: "L3 sequence diagram of the four-check probe in verify_precommit_active.py: binary, config, git hook, and canary checks, with fail-closed JSON output and exit-code semantics."
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
  - docs/architecture/adrs/ADR-017-worktree-quality-gate-guard.md
related_adrs:
  - ADR-017
tags:
  - probe
  - four-check
  - fail-closed
  - canary
---

# Probe Execution — Four-Check Sequence

This diagram shows how a lifecycle gate invokes the probe
`verify_precommit_active.py` and how `run_checks()` orchestrates the four
checks (A–D) that together prove pre-commit hooks will actually fire in the
current working tree.

> **Fail-closed and collect-all.** `run_checks()` runs *all four* checks in
> order (it does not stop at the first failure). Each check that returns `False`
> — including any that raises, such as a canary `TimeoutExpired` — has its key
> appended to `failing_checks`. `main()` then exits `1` when `failing_checks`
> is non-empty, or `0` when it is empty.

---

```mermaid
sequenceDiagram
    autonumber
    participant Gate as Lifecycle Gate
    participant Main as main()
    participant Run as run_checks()
    participant A as check_a_binary_on_path
    participant B as check_b_config
    participant C as check_c_git_hook
    participant D as check_d_canary

    Gate->>Main: python verify_precommit_active.py
    Main->>Run: run_checks()

    Run->>A: Check A — pre-commit binary on PATH?
    A-->>Run: shutil.which("pre-commit") is not None
    Note over Run: On True → binary=true; else append "binary"

    Run->>B: Check B — .pre-commit-config.yaml resolves + parses + non-empty?
    B-->>Run: _resolve_config_path + yaml.safe_load
    Note over Run: On True → config=true; else append "config"

    Run->>C: Check C — shared git hook contains "pre-commit" sentinel?
    C-->>Run: _resolve_git_commondir → hooks/pre-commit
    Note over Run: On True → git_hook=true; else append "git_hook"

    Run->>D: Check D — canary emits PRECOMMIT_CANARY_OK? (10s timeout)
    D-->>Run: subprocess precommit_canary.py
    Note over Run: On True → canary=true; else append "canary"\n(any exception is caught → False)

    Run-->>Main: {binary, config, git_hook, canary, failing_checks}

    alt failing_checks is empty
        Main-->>Gate: stdout {"binary":true,"config":true,"git_hook":true,"canary":true,"failing_checks":[]}
        Main-->>Gate: sys.exit(0)
    else one or more checks failed
        Main-->>Gate: stdout {..., "failing_checks":["config","canary"]}
        Main-->>Gate: sys.exit(1)
    end
```

Parent: [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md)

---

## The four checks

| Key | Function | Passes when |
|---|---|---|
| `binary` | `check_a_binary_on_path` | `shutil.which("pre-commit")` locates the executable on `PATH`. |
| `config` | `check_b_config` | `.leafcutter/pre-commit-config.yaml` (then `.pre-commit-config.yaml`) resolves, parses as YAML, and is non-empty. |
| `git_hook` | `check_c_git_hook` | The shared `hooks/pre-commit` (via `_resolve_git_commondir`) contains the `pre-commit` sentinel string. |
| `canary` | `check_d_canary` | `precommit_canary.py` prints `PRECOMMIT_CANARY_OK` within the 10-second timeout. |

## Output and exit semantics

- **All pass:** JSON `{"binary": true, "config": true, "git_hook": true, "canary": true, "failing_checks": []}` and `exit 0`.
- **Any fail:** `failing_checks` names each failed key (in A→B→C→D order) and `exit 1`.
- **Fail-closed:** exceptions never propagate out of `run_checks()`; the affected check is marked `False` and its key appears in `failing_checks`.

## Cross-References

- [Worktree Quality Gate Guard — Container Overview](../components/worktree-quality-gate-guard.md) — parent container.
- [Gates Sequence](gates-sequence.md) — the three gates that invoke this probe.
- [ADR-017 — Worktree Quality Gate Guard](../adrs/ADR-017-worktree-quality-gate-guard.md).

<!--
====================================================================
DECISION HISTORY
====================================================================
- 2026-07-06 [architecture-diagram-author, EPIC-WorktreeQualityGateGuard/08]:
  Initial creation (BO-1700a-11). Models run_checks() collect-all behaviour
  (all four checks run; each failure appended to failing_checks) rather than
  fail-fast, matching the implementation in verify_precommit_active.py.
====================================================================
-->
