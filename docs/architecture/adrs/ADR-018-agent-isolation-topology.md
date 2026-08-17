---
title: "ADR-018: Agent Isolation Topology — Per-Feature Clones + Hub Branch-Protection, Retire Shared-Worktree Drives"
description: "Records the decision to isolate each parallel coding-agent drive in its own independent git clone (own object store) instead of a git worktree sharing one .git, to make main structurally unmodifiable except through a gated PR + merge-queue workflow on an authoritative hub, and to cap agents-per-feature (not features-in-flight). Motivated by repeated 0-byte-object / poisoned-index corruption of the shared .git under ~16 concurrent autonomous committers, and by 2025-2026 research showing every SOTA autonomous-agent product isolates each agent's checkout+object-store and integrates via PR. Includes a worktree-agent -> clone-agent migration plan and the impact on the in-flight BO-1600 guardrail ACs."
type: "adr"
status: "active"
created: "2026-07-06"
last_updated: "2026-07-06"
deciders:
  - leafcutter-engineering-team
components:
  - worktree_manager
  - build_pipeline
  - commit_guardian
related_docs:
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/adrs/ADR-006-flatten-supervisor-chain.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
related_code:
  - templates/skills/feature/SKILL.md
  - templates/agents/worktree-agent.md
---

# ADR-018: Agent Isolation Topology — Per-Feature Clones + Hub Branch-Protection, Retire Shared-Worktree Drives

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-07-06 |
| Deciders | leafcutter engineering team |
| Author | leafcutter engineering team |
| Supersedes | The shared-`.git` git-worktree model as the isolation primitive for autonomous epic/feature drives (partially reframes ADR-031 and the BO-1600 guardrail ACs — see §Impact on in-flight ACs) |

> Component IDs are drawn from `docs/components.json`: `worktree_manager` (owns
> the per-drive isolation lifecycle this ADR changes), `build_pipeline`
> (`_bootstrap` + template deployment that must work in an independent clone),
> and `commit_guardian` (the pre-commit gate chain that enforces workflow at the
> local edge). `build-orchestration` from prior stubs is not a registered ID;
> `build_pipeline` is the closest registered equivalent.

## Context

Leafcutter drives epics and features by creating a git **worktree** per drive
(`worktree-agent`, `templates/skills/feature/SKILL.md`). Git worktrees
deliberately **share one object store and ref namespace** — every worktree under
one repository reads and writes the same `.git/objects` and `refs/`
(git-worktree docs: worktrees share everything except per-worktree files such as
`HEAD` and `index`). This is the correct, lightweight model for a *small number
of interactive, human-paced sessions* — which is exactly the use case the
upstream Claude Code `--worktree` feature targets.

It is the wrong isolation primitive for **many autonomous agents committing
concurrently**. During this project's own drives we ran on the order of a dozen
concurrent agent sessions across ~17 worktrees sharing one `.git`, and repeatedly
corrupted that shared object store: **0-byte "shadow" loose objects**, a
**poisoned index cache-tree**, and refs pointing at half-written commits — each
requiring manual `find -empty -delete` + `git fetch --refetch` + `read-tree HEAD`
recovery mid-drive. The mechanism is documented, not incidental:

1. **Ordinary `git commit` triggers background auto-gc.** `gc.auto` fires at
   ~6700 loose objects with `gc.autoDetach=true` (detached, in the background),
   so N concurrent committers produce N concurrent auto-gc/repack passes against
   the shared store.
2. **Concurrent gc is documented to risk corruption.** git-gc: "when `git gc`
   runs concurrently with another process, there is a risk of it deleting an
   object that the other process is using but hasn't created a reference to …
   [this] may corrupt the repository."
3. **Loose objects are not fsync'd by default** (pre-`core.fsync`), so a commit
   that is interrupted or killed mid-write leaves a renamed path pointing at
   unflushed / zero-length data — the exact "0-byte object" signature we saw.

Two further problems compounded the corruption:

- **A shared, mutable local `main`.** Multiple sessions committed directly onto
  the one local `main` branch of the shared checkout (e.g. scaffold commits
  landing straight on `main`), diverging and clobbering it, and requiring
  `update-ref` surgery to recover. The per-worktree commit-phase lock we already
  ship is **per-worktree**, so it does not serialize writers across the shared
  object store, and nothing prevented direct-to-`main` commits at the local edge.
- **Over-parallelization.** Running ~16 concurrent drivers is past the productive
  band for coordinated multi-agent work (see Alternatives / evidence).

A 2025-2026 review of the field confirms the topology is the problem, not the
tuning. **Every mainstream product built for many autonomous concurrent agents —
Cursor background agents, OpenAI Codex cloud, GitHub Copilot coding agent, Google
Jules, Cognition Devin, OpenHands — gives each agent its own isolated environment
with its own independent checkout, works on its own branch, and integrates via a
pull request.** None of them run N autonomous committers against a single shared
object store. The only tool that relies on shared-object worktrees (upstream
Claude Code `--worktree`) uses them for interactive file-edit isolation among a
handful of sessions, which is a different workload.

This ADR records the resulting decision: **isolate each drive in its own clone,
and make `main` structurally unmodifiable except through a gated workflow.**

## Decision

### 1. Per-feature isolation = an independent clone with its own object store

Each autonomous drive runs in an **independent working copy that has its own
`.git` object store** — not a worktree sharing the repository's `.git`. Concurrent
commits, refs, and auto-gc in one drive then physically cannot touch another
drive's object store, which eliminates the shared-store corruption class at the
root rather than detecting or recovering from it.

Creation strategy, in order of preference on the leafcutter dev host (native
ext4):

1. **`cp --reflink=auto` of a warm local clone** — copy-on-write, near-instant,
   negligible disk until divergence, and a fully independent object store. This
   gives the disk economy people mistakenly expect from worktrees *with* real
   isolation.
2. **`git clone --reference <local-cache> --dissociate <hub>`** — fast via the
   shared cache, then `--dissociate` copies borrowed objects so the clone is
   decoupled and safe to gc independently.
3. **Plain `git clone`** — the always-correct fallback.

Object-store sharing shortcuts (`git clone --shared` / `--reference` *without*
`--dissociate`, or `git worktree`) are **not** used for autonomous drives: git
documents `--shared`/`--reference` as "possibly dangerous" precisely because a gc
in one repo can corrupt the borrower.

### 2. `gc.auto=0` during drives; single-writer gc between drives

Every drive clone (and the hub) sets `gc.auto=0` and `maintenance.auto=false`
for the duration of a drive, so no background repack races a live writer. Garbage
collection runs exactly once, single-writer, **between** drives
(`git maintenance run` / `git gc`). Even with per-clone isolation this removes the
last in-clone concurrency hazard and is cheap insurance.

### 3. Cap agents-per-feature, never features-in-flight

Two independent axes, only one of which is capped:

- **Agents collaborating on one feature/task** → **capped** (small; ~3-4). This is
  where coordination overhead and error amplification appear (see evidence).
- **Independent features in flight** → **uncapped by design.** This is a human
  team building many features in parallel; with per-clone isolation there is no
  shared-state reason to limit it. The only real ceiling is host resources
  (locally, RAM/CPU) — which is a scheduling concern, not a correctness one, and
  is the point at which cloud per-agent sandboxes (the vendor model) take over to
  make it genuinely unbounded.

The prior guidance to "cap concurrency" conflated these; this ADR separates them.

### 4. `main` is unmodifiable except through a gated workflow (the hard guarantee)

The authoritative `main` lives on the **hub** (the `origin` remote). No agent —
regardless of local behaviour — may change it except through the workflow. The
guarantee is **server-side**, because any local control is bypassable
(`--no-verify`, direct `git push`) and therefore cannot be a guarantee:

**Remote (authoritative) — the actual guarantee, on the hub's `main`:**

- Disallow **direct pushes**; require a pull request.
- Require **status checks** to pass (ruff, full test suite, schema-diff) — as
  *required* checks, not advisory.
- Require the **merge queue** — merges are serialized, built against the latest
  `main`, and performed *by the queue*, not by an agent.
- Disallow **force-push** and **branch deletion** on `main`.
- **Do not allow bypassing the above** — no admin/owner shortcut. This is the
  setting that converts "convention" into "impossible": even a privileged token
  or `gh pr merge --admin` cannot land on `main` outside the gate.

**Credentials:** agents authenticate as a least-privilege machine identity with
**no bypass permission and no direct-push right** to `main`. Combined with branch
protection, the *capability* to mutate `main` directly does not exist for agents.

**Merge authority:** an agent's authority ends at "open PR." The gated queue
performs the merge when checks are green. No agent step runs `git push origin
main` or an ungated `gh pr merge`.

**Local (defense-in-depth, advisory only):** each drive clone's `origin` points
only at the hub; a `pre-push`/`pre-commit` hook refuses commits or pushes
targeting `main`. This catches mistakes early but is explicitly *not* the
guarantee — the remote is. There is no shared local `main` that agents commit
into; a clone's `main` is a read-only tracking branch.

The clone topology reinforces the guarantee structurally: an agent in its own
clone can reach the authoritative `main` only via a push that protected `main`
rejects unless it flows through PR + required checks + merge queue.

### 5. Keep `files_touched` partitioning — it is orthogonal

The existing physical-parallelism gate (schedule concurrent drives so their
`files_touched` sets are disjoint) is retained. It prevents *content* merge
conflicts; it does **not** address object-store safety. The two are orthogonal
and both are needed: partitioning keeps merges clean; per-clone isolation keeps
the object store uncorrupted.

## Migration Plan

Phased; docs/ADR first (this change), code changes deferred to their own tickets.

1. **Harden the hub `main` branch protection (highest leverage, no code).**
   Configure on the `origin` repo: required PR, required checks (ruff + tests +
   schema-diff), enable **merge queue**, block force-push/deletion, and **disable
   bypass**. This immediately makes "an agent changed `main` outside the workflow"
   impossible, independent of the topology work below.

2. **Immediate corruption mitigation while still on worktrees (no code):** set
   `gc.auto=0` + `maintenance.auto=false` on the shared repo during drives; run
   `git gc` only single-writer between drives; keep drives on native ext4 (never
   `/mnt/c`, network, or portable drives). This buys safety before the clone work
   lands.

3. **`worktree-agent` -> `clone-agent`.** Change the isolation primitive behind
   the existing agent/skill abstraction:
   - Replace `git worktree add <path> origin/<base>` with an independent clone
     (`cp --reflink=auto` of a warm clone → fallback `git clone --reference …
     --dissociate` → fallback `git clone`).
   - Point the clone's `origin` at the hub; create the feature branch there.
   - Run `build.py`/`_bootstrap` inside the clone (it already deploys everything
     needed; confirm it works against an independent clone, not just a worktree).
   - Set `gc.auto=0` in the clone.
   - Keep the interface (`create`/`remove`, ticket-path routing) stable so
     `/build-feature`, `build-single-ticket`, and finalize call sites are
     unchanged; only the lifecycle mechanism swaps.
   - `remove` deletes the clone directory and its branch (no `git worktree
     remove` semantics needed).

4. **Retire the shared-local-`main` pattern.** No drive step commits to a local
   `main`. Scaffold/finalize bookkeeping that today lands on local `main` moves
   to a branch + PR (as several scaffold PRs in practice already do). Sync of a
   developer's local `main` becomes read-only (`fetch` + fast-forward only).

5. **Finalize/merge via the queue.** Update finalize so the merge is a
   queue-eligible PR action, not an agent-issued `gh pr merge`; the queue lands it
   when green.

6. **Fleet scheduling.** Cap agents-per-drive (~3-4) in the drive runbook; do not
   cap the number of independent drives. Add a host-resource-aware scheduler
   (shed idle drives under memory pressure, mirroring upstream Claude Code's
   supervisor behaviour) rather than a fixed feature cap.

## Impact on in-flight ACs (BO-1600 / BP-1100e / INF-600l)

The three guardrail epics scaffolded on 2026-07-06 assume the shared-worktree
model. This ADR changes that assumption, so they must be resequenced before build:

- **BO-1600a / BO-1600b / BO-1600c (prevention: serialize commit phases,
  interrupted-commit safety, detect-and-halt on corruption)** — **largely
  obsoleted / to revise.** Per-clone isolation makes cross-drive object-store
  corruption structurally impossible, so the *prevention* these ACs describe is
  mostly unnecessary. Do not build them as written; re-scope to the residual
  in-clone case (which `gc.auto=0` already covers) or drop.
- **BO-1600d (EPIC-GuidedGitRecovery — human-invoked, dry-run-first recovery
  helper)** — **keep as a safety net, lower priority.** Corruption should become
  rare under clones, but a portable recovery helper remains valuable for the
  `/mnt/c`/interrupted-process cases and for consumer projects. De-prioritize
  relative to the topology change.
- **BP-1100e (EPIC-PhantomDoneFilesTouched — files_touched vs diff
  reconciliation)** — **keep, unchanged.** Content-conflict / phantom-done
  prevention is orthogonal to isolation topology (Decision §5) and is still the
  highest-value guardrail.
- **INF-600l (EPIC-RegistryCardMirror — registry↔card mirror consistency)** —
  **keep, unchanged.** Unrelated to isolation.

Net: **build BP-1100e and INF-600l as planned; hold and re-scope BO-1600a/b/c;
keep BO-1600d as a de-prioritized safety net.** The real fix for the corruption
class is this ADR's topology change, not the BO-1600 prevention ACs.

## Consequences

**Positive:**

- **Corruption class eliminated at the root.** Independent object stores mean
  concurrent commits/gc across drives cannot corrupt each other — no detection or
  recovery machinery required for the common case.
- **`main` is provably gated.** Server-side branch protection with no bypass makes
  ungated changes to `main` impossible, not merely discouraged.
- **Feature parallelism scales like a human team.** With isolation, more parallel
  *features* is safe; the only ceiling is compute, and cloud sandboxes lift even
  that.
- **Simpler mental model.** "One clone = one developer's laptop; the hub = the
  shared remote; PRs + merge queue = the team's process" replaces the subtle
  shared-object-store reasoning that kept biting.

**Negative / accepted tradeoffs:**

- **Disk cost.** Independent clones cost more than worktrees; `cp --reflink` (COW)
  on ext4/btrfs mitigates this substantially, but it is real.
- **Clone/bootstrap latency.** Creating an independent clone and running
  `_bootstrap` is slower than `git worktree add`. Reflink copies keep this small;
  it is accepted as the price of isolation.
- **Merge-queue latency.** Serialized, build-against-latest merges are slower to
  land than a direct squash-merge. This is the intended cost of never breaking
  `main`.
- **Migration surface.** `worktree-agent`, `feature` SKILL, finalize, and the
  drive runbook all change. Kept behind the existing agent interface to bound the
  blast radius.

**Operational:**

- Runs must stay on a native POSIX filesystem (ext4/btrfs/xfs); `/mnt/c` DrvFs,
  network shares, and portable drives weaken rename atomicity / fsync durability
  and cause 0-byte objects independent of concurrency.
- ADR-031's Worktree Quality Gate Guard still applies to any residual worktree
  usage and to the clone bootstrap: the gate-readiness (pre-commit hooks actually
  fire) invariant is unchanged; only the isolation container changes.

## Alternatives Considered

- **Keep worktrees, add a global commit lock + `gc.auto=0`.** Serialize all
  writers across the shared object store with a repository-global lock and disable
  auto-gc. Rejected as the primary design: it re-imposes a global serialization
  bottleneck (killing the parallelism we want), the lock is easy to bypass or
  leak, and it still shares one object store — one stray `gc`/`repack`/`prune` or
  killed-mid-commit process reintroduces the corruption. It is retained only as
  the *interim* mitigation (Migration step 2) until clones land.

- **Cap features-in-flight to a small number.** Limit total concurrent drives.
  Rejected: it throttles legitimate parallel feature work (the explicit goal) to
  work around a topology defect instead of fixing it. The correct cap is
  agents-*per-feature*, not features.

- **Cloud sandbox per agent now (Cursor/Codex/Jules model).** One VM/container per
  drive with its own clone. Not rejected — it is the *stronger* form of Decision
  §1 and the natural end state for unbounded, untrusted-code-safe parallelism.
  Deferred because per-clone-on-native-FS captures the corruption fix locally with
  far less infrastructure; the container/VM step can layer on later without
  changing the isolation contract.

- **Rely on local hooks to protect `main`.** Block direct-to-`main`
  commits/pushes with pre-commit/pre-push hooks only. Rejected as the guarantee:
  local hooks are bypassable (`--no-verify`) and absent in fresh clones until
  built; they are kept as defense-in-depth but the guarantee must be server-side
  branch protection.

- **Do nothing / recover-on-corruption (the BO-1600 prevention ACs).** Detect and
  repair shared-store corruption as it happens. Rejected as the primary strategy:
  it treats a structural defect as an operational one. Recovery (BO-1600d) is
  worth keeping as a safety net, but designing the system so corruption cannot
  occur is strictly better than making it recoverable.

## References

- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md) — the
  template-source / deployed-output boundary the clone bootstrap must honour.
- [ADR-006 — Flatten Supervisor Chain](ADR-006-flatten-supervisor-chain.md) — the
  dispatch topology whose drives this ADR re-hosts in clones.
- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md)
  — the fail-closed gate-readiness invariant that still applies to the clone
  bootstrap; this ADR changes the isolation container, not the gate.
- git-worktree (shared `.git/objects` + `refs/`; "experimental"):
  https://git-scm.com/docs/git-worktree
- git-gc (concurrent gc corruption risk; `gc.auto`/`gc.autoDetach`;
  `--prune=now`): https://git-scm.com/docs/git-gc
- git-clone (`--shared`/`--reference` "possibly dangerous"; `--dissociate`;
  `--local` hardlinks): https://git-scm.com/docs/git-clone
- Git 2.36 `core.fsync` / `core.fsyncMethod` (loose-object durability):
  https://github.blog/open-source/git/highlights-from-git-2-36/
- GitHub merge queue (FIFO, build-against-latest, serialized merge):
  https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/configuring-pull-request-merges/managing-a-merge-queue
- Vendor per-agent isolation: Cursor background agents
  (https://cursor.com/docs/background-agent), OpenAI Codex cloud
  (https://developers.openai.com/codex/cloud), GitHub Copilot coding agent
  (https://docs.github.com/en/copilot/concepts/agents/coding-agent/about-coding-agent),
  Google Jules (https://jules.google/docs), OpenHands runtime
  (https://docs.openhands.dev/usage/architecture/runtime).
- Google/MIT, "Towards a Science of Scaling Agent Systems" (Dec 2025) —
  diminishing/negative returns past a small agent count; centralized coordination
  contains error amplification: https://arxiv.org/abs/2512.08296
