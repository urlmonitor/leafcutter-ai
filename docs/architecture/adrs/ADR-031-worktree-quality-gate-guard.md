---
title: "ADR-031: Worktree Quality Gate Guard — Execution-Proof Fail-Closed Design"
description: "Records the design of the worktree quality gate guard: a four-check probe model (binary, config, git_hook, canary) whose canary check requires the hook chain to actually FIRE, a fail-closed-on-self-error invariant with no fail-open path, an index-0 self-healing hook that re-materialises the pre-commit config, dual create-time and pre-drive gates, template/deployed source parity per ADR-001, and supersession of the interim one-file feature/SKILL.md slice (commit 586d6191). Motivated by the fresh-worktree silent-skip failure mode surfaced in the EPIC-AcPipelineDeployGaps retrospective."
type: "adr"
status: "active"
created: "2026-07-06"
last_updated: "2026-07-06"
deciders:
  - leafcutter-engineering-team
components:
  - worktree_manager
  - precommit_hooks
  - build_pipeline
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/retrospectives/EPIC-AcPipelineDeployGaps.md
related_code:
  - templates/skills/feature/SKILL.md
---

# ADR-031: Worktree Quality Gate Guard — Execution-Proof Fail-Closed Design

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-07-06 |
| Deciders | leafcutter engineering team |
| Author | adr-author (leafcutter engineering team) |
| Supersedes | Interim one-file `templates/skills/feature/SKILL.md` slice (commit `586d6191`) |

> Component IDs above are drawn from `docs/components.json`. The guard spans four
> registered components: `worktree_manager` (owns worktree lifecycle and
> create-time gating), `precommit_hooks` (the config and hook chain being
> guarded), `build_pipeline` (`_bootstrap` create-time gate and template
> deployment), and `commit_guardian` (the self-check probe scripts live under the
> guardian script tree). `build-orchestration` from the ticket stub is **not** a
> registered ID; `build_pipeline` is the closest registered equivalent and is
> used here.

## Context

During the EPIC-AcPipelineDeployGaps drive (2026-06-17), **every package
pre-commit hook was silently skipped for the entire epic drive**
(retrospective Finding #2, the highest-value finding). Epic worktrees are
created from `origin/main`, and `.pre-commit-config.yaml` is not a tracked
file — it is a `.leafcutter` symlink established by `install_shims` in the
main working tree only. A fresh worktree therefore has neither the symlink nor
a populated `.leafcutter/`. When `.pre-commit-config.yaml` is absent, `git
commit` runs with `PRE_COMMIT_ALLOW_NO_CONFIG=1` and **passes without running a
single hook** — no error, no warning, no non-zero exit. The drive completed
"green" while quality gates were entirely inert.

The damage was invisible until after merge: a post-drive diagnostic found 14
would-have-blocked findings (7 `check-feedback-id` + 7 `check-description-field`)
that required a dedicated post-merge fix commit (`25adec3`). The failure was not
that a gate rejected bad work — it was that the gate **did not exist at commit
time and said nothing about its own absence**. This is a silent-skip failure
mode: the protective mechanism disappears and the pipeline reports success.

An interim mitigation shipped in commit `586d6191`
(`fix(feature): fail-closed pre-commit config recovery in epic worktree
bootstrap`). It patched a single file — `templates/skills/feature/SKILL.md` — to
run a mandatory fail-closed recovery (attempt symlink, then copy fallback,
re-probe, HARD HALT if still absent) in the epic worktree bootstrap step. That
slice closed the epic-path bypass but left three structural gaps:

1. **Presence is not execution.** The interim slice proves the config *file* can
   be established; it does not prove the hook chain actually *runs*. A present
   but mis-wired config, an empty hook list, or a broken interpreter path all
   pass a presence check while still skipping enforcement at commit time.
2. **One gate, one code path.** Recovery lived only in the feature SKILL bootstrap
   prose. Worktrees created by other paths (`build.py` `_bootstrap`, direct
   `worktree-agent` create, manual clone) had no equivalent guard, so a competing
   unguarded path remained.
3. **No source-of-truth parity.** A one-file SKILL edit does not carry the
   template → deployed parity guarantee that ADR-001 requires for any script that
   also runs inside consumer projects.

This ADR defines the durable design — the **Worktree Quality Gate Guard** — that
replaces the interim slice with an execution-proof, fail-closed, dual-gated,
self-healing mechanism.

## Decision

### 1. The four-check probe model (canary execution is non-negotiable)

The guard verifies quality-gate readiness with **four ordered checks**, all of
which MUST pass before work is allowed to proceed:

| Check | Question it answers | Pass condition |
|---|---|---|
| `binary` | Is the `pre-commit` executable resolvable and runnable? | Binary is found on `PATH` (or the pinned venv) and reports its version. |
| `config` | Does `.pre-commit-config.yaml` exist and parse as a non-empty hook set? | File is present, is valid YAML, and declares at least one hook. |
| `git_hook` | Is the git `pre-commit` hook installed and pointing at the framework? | `.git/hooks/pre-commit` (resolved for the worktree's `commondir`) invokes the pre-commit framework. |
| `canary` | Does the hook chain **actually FIRE** on a commit attempt? | A staged canary change triggers a real hook run whose observable side effect (a hook executing) is captured; the canary is then reverted. |

The `canary` check is **non-negotiable and MUST NOT be reduced to a presence
check**. The three preceding checks establish that the machinery *looks* correct;
only the canary establishes that it *works*. The EPIC-AcPipelineDeployGaps failure
passed every presence-style condition a naive check would test (a repo existed, a
git dir existed, commits succeeded) and still ran zero hooks. The guard therefore
requires positive evidence of execution — the hook chain firing — not evidence of
installation. "Present" is insufficient; only "FIRES" satisfies the guard.

### 2. Fail-closed-on-self-error invariant (no fail-open path exists)

The guard MUST fail closed. If **any** of the four checks fails, **or if the
guard itself errors** (probe script raises, times out, cannot resolve a path,
cannot read the config, or hits any unexpected condition), the guard MUST HARD
HALT the operation it gates. There is **no fail-open branch**: the guard never
degrades to a warning, never continues on error, and never treats "I could not
determine the answer" as "the answer is yes."

This is the direct inversion of the original defect, where an
undeterminable/absent state (`PRE_COMMIT_ALLOW_NO_CONFIG=1`) was treated as
permission to proceed. The invariant is: **an unproven gate is a failed gate.**
An operator who genuinely wants to bypass enforcement must do so through an
explicit, auditable, human-authorised mechanism — never through the guard's
silent tolerance of its own uncertainty.

### 3. Index-0 self-healing hook to guarantee config presence

To make the guard's `config` check *satisfiable* in a fresh worktree rather than
merely *diagnostic*, the guard registers a **self-healing hook at index 0** — the
first hook in the chain. Registered first, it runs before any other hook on every
commit and is responsible for re-materialising `.pre-commit-config.yaml` (via the
symlink-then-copy strategy) if it has gone missing. Because it holds index 0, no
enforcement hook can run against a stale or absent config: the config is repaired
at the head of the chain, then the remaining hooks execute against the
guaranteed-present config. This converts config presence from a precondition the
operator must remember into an invariant the chain maintains itself.

### 4. Dual gates: create-time (`_bootstrap`) + pre-drive (SKILL)

A single gate is insufficient because worktrees are born and consumed through
different paths. The guard is therefore installed at **two independent gates,
and both are required**:

- **Create-time gate — `build.py` `_bootstrap`.** When a worktree is
  bootstrapped, the guard runs the four-check probe and HARD HALTs creation if
  the worktree cannot be made gate-ready. This catches the failure at the
  earliest possible moment and prevents an unguarded worktree from ever existing.
- **Pre-drive gate — the driving SKILL.** Immediately before a drive begins, the
  SKILL re-runs the four-check probe against the worktree it is about to drive and
  HARD HALTs the drive if the gate is not proven. This catches drift between
  creation and use (a config deleted, a hook uninstalled, a symlink broken since
  bootstrap) and covers worktrees created by paths that did not pass through
  `_bootstrap`.

Both gates are mandatory. Create-time alone cannot cover post-creation drift or
externally-created worktrees; pre-drive alone cannot prevent an unguarded
worktree from being created and used by a path that skips the SKILL. Together
they close the "born unguarded" and "drifted to unguarded" windows.

### 5. Template/deployed source parity for all three guard scripts (ADR-001)

The guard is implemented as **three scripts** (the probe/canary runner, the
self-healing index-0 hook, and the gate entrypoint invoked by both gates). Per
[ADR-001](ADR-001-self-hosting-boundary.md), each of the three MUST have
**template/deployed source parity**: the authoritative source lives in the
tracked package template tree, and `build.py` deploys it to the consumer/worktree
location. The deployed copy is a build output, never hand-edited. This guarantees
that a fresh clone or consumer install carries everything needed to build and run
the guard, and that the guard behaves identically in the leafcutter self-host and
in any consumer project. A guard that only existed in a deployed (untracked)
location would itself vanish in a fresh worktree — reproducing the exact class of
bug it is designed to prevent.

### 6. Supersession of the interim one-file SKILL.md slice (586d6191)

This design **supersedes** the interim fix in commit `586d6191`. That commit is
retained in history as the first mitigation, but the durable guard replaces it so
that **no competing recovery path remains**. Once the guard's dual gates and
self-healing hook are in place, the ad-hoc recovery prose in
`templates/skills/feature/SKILL.md` is removed/redirected to call the guard, so
there is exactly one implementation of worktree gate recovery. Leaving both in
place would risk divergent behaviour between the epic-feature path and every other
path — the very fragmentation (gap #2 above) that motivated this ADR.

## Consequences

**Positive:**

- **No silent skips.** The canary check makes "the hook chain did not fire" a
  detectable, halting condition instead of an invisible success. The class of bug
  behind EPIC-AcPipelineDeployGaps Finding #2 becomes impossible to reach silently.
- **Fail-closed by construction.** Because there is no fail-open branch, any
  uncertainty about gate readiness stops the operation rather than waving it
  through. The default is safety.
- **Portable protection.** Template/deployed parity (ADR-001) means the guard
  works identically in the leafcutter self-host, in fresh clones, in CI, and in
  consumer projects — the guard cannot itself go missing in a fresh worktree.
- **Setup-free activation.** The index-0 self-healing hook re-materialises the
  config automatically, so operators do not have to remember the manual
  symlink/copy step. Gate readiness becomes a maintained invariant, not a manual
  checklist item.
- **Single code path.** Superseding the interim slice removes the competing
  recovery path; there is one guard, invoked at both gates.

**Negative / accepted tradeoffs:**

- **Commit-time and create-time cost.** The canary check performs a real
  (immediately reverted) commit-path exercise, and the index-0 hook runs on every
  commit. This adds latency to worktree creation and to each commit. The cost is
  accepted as the price of execution proof — a presence check is cheaper but does
  not prevent the failure mode.
- **Three scripts to maintain under parity.** The template/deployed parity rule
  means each of the three guard scripts must be edited in the template tree and
  redeployed via `build.py`; hand-editing a deployed copy is a parity violation.
  This convention must be known and is enforced by build guards.
- **Hard halts are disruptive by design.** A drive or a worktree creation that
  cannot prove its gate will stop. This is intentional — a stopped drive is
  recoverable; a silently ungated drive is not — but it means transient
  environment problems surface as halts rather than warnings.

**Operational:**

- The self-healing hook uses the same symlink-first, copy-fallback strategy as
  `install_shims` (consistent with ADR-001 and the worktree pre-commit bootstrap
  guidance in `CLAUDE.md`), so it introduces no new failure modes beyond those
  already handled for shims.
- Because the guard fails closed, any bypass for a genuinely intended
  no-enforcement situation must go through an explicit, human-authorised path
  (e.g. an audited `--no-verify` with recorded authorisation), never through
  guard tolerance.

## Alternatives Considered

- **Presence-only check (the interim `586d6191` slice).** Verify that
  `.pre-commit-config.yaml` can be established, then proceed. Rejected as the
  primary design: presence does not imply execution. A present-but-inert config
  (empty hook list, broken interpreter, mis-wired git hook) passes presence and
  still skips enforcement — the exact gap this ADR closes. Retained only as the
  historical first mitigation that this ADR supersedes.

- **Advisory warning instead of hard halt (fail-open).** Log a warning when the
  gate is unproven and let the operation continue. Rejected: this reproduces the
  original defect, where an undeterminable state was treated as permission to
  proceed. Warnings during long drives are not read in time; the 14 post-merge
  findings prove that a non-halting signal is equivalent to no signal.

- **Single gate (create-time only, or pre-drive only).** Rejected: create-time
  alone cannot cover post-creation drift or worktrees created by paths that skip
  `_bootstrap`; pre-drive alone cannot stop an unguarded worktree from being
  created and consumed by a path that skips the SKILL. Only the dual gate closes
  both the "born unguarded" and "drifted to unguarded" windows.

- **Track `.pre-commit-config.yaml` (and guard scripts) directly in git.**
  Commit the config and deployed scripts so fresh worktrees inherit them without a
  build step. Rejected: this violates the ADR-001 self-hosting boundary
  (`.leafcutter/` and its outputs are build artifacts, not tracked source),
  creates `git status` noise, and breaks on Windows/WSL2 where tracked symlinks
  fail silently. Template/deployed parity achieves the portability goal without
  committing build outputs.

- **Keep both the interim slice and the new guard.** Leave `586d6191`'s recovery
  prose in place alongside the guard. Rejected: two recovery paths risk divergent
  behaviour between the epic-feature path and all other paths — the fragmentation
  that motivated this ADR. There must be exactly one guard implementation.

## References

- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) —
  establishes the template-source / deployed-output boundary that the guard's
  three scripts follow (Decision §5).
- [EPIC-AcPipelineDeployGaps retrospective](../../retrospectives/EPIC-AcPipelineDeployGaps.md)
  — Finding #2 (all package hooks silently skipped for the entire drive) and
  Finding #2B (14 metadata findings required a post-drive fix commit) are the
  motivating failure mode (Context).
- Commit `586d6191` — `fix(feature): fail-closed pre-commit config recovery in
  epic worktree bootstrap`, the interim one-file `templates/skills/feature/SKILL.md`
  slice superseded by this ADR (Decision §6).
