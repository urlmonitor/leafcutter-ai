---
title: "EPIC: Worktree Quality Gate Guard"
type: epic
status: todo
components:
  - build-orchestration
created: 2026-07-02
depends_on: []
priority: high
---

# EPIC: Worktree Quality Gate Guard

Code can never ship from a workspace with its quality gates switched off. A fail-closed, portable guard that PROVES pre-commit hooks actually fire in a worktree before a build drive proceeds. When work happens in a fresh, throwaway workspace, the automatic quality checks that protect the main line are always active — never silently disabled. If those checks cannot be made to run, the work stops rather than slipping through unchecked. You get the same protection in every workspace, whether the project is building itself or is installed inside another project, and you never have to remember a manual setup step to stay safe.

## Dependency Graph

```
01 (ADR: Design)
  ↓
02 (Probe core + canary + git-common-dir)
  ↓
├─→ 03 (Probe integrity + robustness)
├─→ 04 (Fail-closed invariant + anti-bypass)
├─→ 05 (Self-healing hook)
└─→ 07 (Portability + graceful no-op)
  ↓
06 (Gates: create-time + pre-drive + commit-phase)
  ↓
08 (Docs & diagrams)
```

## Sub-Tickets

| # | File | Description | Status |
|---|------|-------------|--------|
| 01 | [01_adr_worktree_quality_gate_guard_design.md](./01_adr_worktree_quality_gate_guard_design.md) | ADR: worktree quality-gate guard design (execution/canary probe, fail-closed, self-healing, dual gates, portability, supersedes interim SKILL.md slice) | `[ ]` |
| 02 | [02_probe_core_canary_git_common_dir.md](./02_probe_core_canary_git_common_dir.md) | Probe core + canary + git-common-dir resolution (verify_precommit_active.py, precommit_canary.py, build_precommit integration, templates mirrors) | `[ ]` |
| 03 | [03_probe_integrity_robustness.md](./03_probe_integrity_robustness.md) | Probe integrity + robustness (required-hook-ID, anti-spoof, multi-stage, freshness/drift, timeout, hooksPath) | `[ ]` |
| 04 | [04_fail_closed_invariant_anti_bypass.md](./04_fail_closed_invariant_anti_bypass.md) | Fail-closed invariant + anti-bypass (fail-closed-on-self-error, PRE_COMMIT_ALLOW_NO_CONFIG, --no-verify, canary removed) | `[ ]` |
| 05 | [05_self_healing_hook.md](./05_self_healing_hook.md) | Self-healing hook (ensure_precommit_config.py, symlink/copy re-materialization, atomic + idempotent, index-0 manifest registration, templates mirror) | `[ ]` |
| 06 | [06_gates_create_time_pre_drive_commit_phase.md](./06_gates_create_time_pre_drive_commit_phase.md) | Gates: create-time + pre-drive + commit-phase (setup_ticket_worktree.py _bootstrap, building-epics SKILL §1.0.1, commit.md, all consuming probe) | `[ ]` |
| 07 | [07_portability_graceful_no_op.md](./07_portability_graceful_no_op.md) | Portability + graceful no-op (build.py deploys 3 guard scripts, consumer subdir layout, partial-build detection, non-worktree clone, main-tree commits, authoritative no-config) | `[ ]` |
| 08 | [08_docs_diagrams.md](./08_docs_diagrams.md) | Docs & diagrams (how-to verify-precommit-active, probe sequence diagram, self-heal component + sequence, gates sequence diagram) | `[ ]` |

