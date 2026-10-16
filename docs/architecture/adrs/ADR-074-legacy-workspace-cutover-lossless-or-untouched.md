---
title: "ADR-074: Legacy Workspaces Are Cut Over Through the One Maker — Retired When Empty, Brought Over Only When Provably Lossless, Otherwise Left Untouched"
description: "The cut-over from git-worktree workspaces to per-feature clones runs as one verb of the workspace maker (worktree.py migrate-legacy), the only code allowed to run git worktree commands, and only against legacy entries. A legacy workspace holding nothing unsent is retired; one holding unsent work is brought over only when every commit and every uncommitted byte is proven present in the new clone, and otherwise is left exactly as it was and listed for a human decision — because the user decided (Q10) that the cut-over must never retire a workspace that still holds unsent work."
type: "adr"
status: "active"
created: "2026-10-14"
last_updated: "2026-10-14"
deciders:
  - adr-author
  - architect-review
components:
  - worktree_manager
  - build_orchestration
  - build_pipeline
related_docs:
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
  - docs/architecture/adrs/ADR-018-agent-isolation-topology.md
  - docs/architecture/adrs/ADR-031-worktree-quality-gate-guard.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
  - docs/architecture/components/worktree-manager.md
  - docs/reference/workspace-maker-interface.md
  - docs/reference/workspace-maker-answers-and-codes.md
  - docs/analysis/2026-09-25-worktree-isolation-decision-memo.md
  - docs/analysis/2026-09-25-worktree-creation-consolidation.md
  - docs/analysis/2026-09-25-worktree-migration-plan.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300f-3.yaml
  - docs/acceptance-criteria/build-orchestration/BO-4100-sound-workspace-by-construction/BO-4100c-1.yaml
related_code:
  - templates/scripts/worktree.py
  - scripts/build_phases_script_deploy.py
---

# ADR-074: Legacy Workspaces Are Cut Over Through the One Maker — Retired When Empty, Brought Over Only When Provably Lossless, Otherwise Left Untouched

## Status

| Field | Value |
|---|---|
| **Status** | Proposed |
| **Date** | 2026-10-14 |
| **Author** | adr-author (dispatched for ticket BO-4300f-3 after architect-review) |
| **Supersedes** | None. Adopts [ADR-070](ADR-070-single-workspace-maker-and-resolver.md) unchanged and refines its Operational note on the cut-over chore (see Decision §5.2). |

> Component IDs are drawn from `docs/components.json`. `worktree_manager` owns the maker
> and the workspaces the cut-over changes; `build_orchestration` owns the routes whose old
> workspaces are being retired; `build_pipeline` owns the standalone-scripts deploy phase
> that must ship the cut-over's helper module.

## Context

[ADR-070](ADR-070-single-workspace-maker-and-resolver.md) makes every new workspace a
hardlinked per-feature clone made by one maker, `templates/scripts/worktree.py`, and found
by scanning markers rather than by `git worktree list`. That leaves the workspaces made the
old way. The [consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md)
§8 counted 19 registered `git worktree` workspaces in this repository plus WSL
`background-worktrees` admin entries stuck `locked` with reason "initializing" — entries a
Linux shell started and never finished, which Windows git can neither use nor remove with
`git worktree remove`. None of those carry a marker, so the maker cannot see them; all of
them still share the main checkout's `.git`, which is the corruption and hook-sharing class
ADR-070 exists to end ([ADR-018](ADR-018-agent-isolation-topology.md)).

Some of those old workspaces still hold work that has not reached the shared project:
commits on no pushed line, edited tracked files, new untracked files, stashes. The obvious
cut-over — `git worktree prune` and `git worktree remove --force` on everything — destroys
that work silently. At the BA gate on 2026-09-25 the user decided (Q10, recorded on AC
[BO-4300f-3](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300f-3.yaml)):
**a workspace that still holds unsent work is never retired by the cut-over** — it is
brought over, or left untouched and listed for a human decision.

Three further constraints come from ADR-070 and the ticket's architect-review:

- ADR-070 §1.4 forbids any code path other than the maker from creating, locating or
  removing a workspace. A second, free-standing migration script would be exactly the
  sixth path ADR-070 was written to prevent.
- Once ADR-070 lands, nothing else in the package runs `git worktree`. The cut-over is the
  one remaining legitimate reason to run it, so the boundary of that exception has to be
  stated or it widens by accident.
- A helper module the maker imports that is not a named deploy-manifest entry raises
  `ModuleNotFoundError` in the deployed maker (ADR-070 §5.2; the `done_proof.py` incident
  in `CLAUDE.md`).

The cost of not deciding is lost work on the one day the cut-over runs, and a cut-over
mechanism whose safety rule lives only in an AC's notes field.

## Decision

### 1. The cut-over is one verb of the one maker

1. The cut-over MUST be the maker verb `migrate-legacy`, invoked as
   `python <absolute path printed by where> migrate-legacy [--preview] [...]`. It MUST NOT
   be a separate entry-point script.
2. Its logic MUST live in the helper module `templates/scripts/workspace/workspace_migrate.py`,
   imported by `worktree.py`. That module MUST have its own NAMED entry in
   `build_template_standalone_scripts` in `scripts/build_phases_script_deploy.py`
   (including the phase's docstring list), per ADR-070 §5.2. Its only tracked source MUST
   be under `templates/scripts/`.
3. `migrate-legacy` MUST be the only code in the package that runs a `git worktree`
   command, and it MUST run one only against a **legacy entry**: an entry that
   `git worktree list --porcelain` of the main checkout reports, other than the main
   checkout itself. It MUST NOT run a `git worktree` command against the main checkout, and
   it MUST NOT alter, move or remove a marker-bearing clone made by `ensure`.
4. `migrate-legacy` MUST NOT run a blanket `git worktree prune`. Every removal MUST target
   one named entry, so that removing one entry changes nothing else.
5. `migrate-legacy` MUST NOT delete, rename or move a branch or any other ref, MUST NOT
   push to the hub, and MUST NOT change the main checkout's git config. The only state it
   changes is legacy entries' folders and registrations, and the brought-over clones it
   creates through `ensure`.

### 2. Classify every entry first, then act — and an entry that cannot be classified stops the run

1. `migrate-legacy` MUST assign every legacy entry exactly one outcome — `retired`,
   `brought_over` or `needs_decision` — in a planning pass that changes nothing, before it
   makes its first change.
2. The holds-work / holds-nothing verdict MUST be the one defined by AC
   [BO-4100c-1](../../acceptance-criteria/build-orchestration/BO-4100-sound-workspace-by-construction/BO-4100c-1.yaml):
   holds nothing only when every commit on its branch is on its own pushed line or on the
   shared main line (counting content that arrived under a different identifier), and it
   has no uncommitted change other than tracked files the BO-4300c-1-iii build-output rule
   identifies as build output; holds work on any unsent commit, non-build modified tracked
   file, staged change, non-ignored untracked file, or stash entry belonging to it. A second,
   divergent definition MUST NOT be written: when the BO-4100c-1 assessor is delivered as a
   deployed module, `migrate-legacy` MUST call it instead of carrying its own copy.
3. When `migrate-legacy` cannot establish a verdict for an entry, or meets any other
   condition it cannot classify, it MUST answer with an error whose code is
   `INTERNAL_ERROR` and whose message names the entry and the condition. It MUST make no
   change in that run, MUST NOT answer `ok`, and MUST NOT print a traceback on stdout. An
   unclassifiable entry MUST NOT be reported as `needs_decision`: that outcome means "holds
   work and could not be brought over losslessly", and using it for "unknown" would hide a
   maker defect behind an `ok` answer (ADR-070 §3.6).
4. A legacy entry that is locked for any reason other than the stuck-registration case of
   §4 MUST be classified `needs_decision` with reason `locked`, whatever its verdict.

### 3. Holds nothing → retired; holds work → brought over only when provably lossless

1. A legacy entry with the holds-nothing verdict MUST be retired: its folder MUST be
   removed and its registration under the main checkout's `.git/worktrees/` MUST be
   removed, by commands that target that entry alone.
2. A legacy entry with the holds-work verdict MUST NOT be retired unless it has first been
   brought over. It MUST be either brought over (§3.3–§3.5) or left untouched and listed as
   `needs_decision`.
3. A brought-over workspace MUST be made by the same `ensure` path every other workspace is
   made by (ADR-070 §2): a marker-bearing clone with real install files and canary-proven
   hooks (ADR-031). `migrate-legacy` MUST NOT hand-build a workspace.
4. Bringing over is **provably lossless** only when all of the following are verified in
   the new clone after the transfer: every commit SHA reachable from the legacy branch's
   head is present and reachable from the new line of work's head; every modified and
   staged tracked file has byte-identical content; every non-ignored untracked file is
   present with byte-identical content; and every stash entry belonging to the legacy
   workspace is present. Unsent commits MUST be transferred from the main checkout's own
   object store, never by pushing them to the hub. A legacy workspace whose state cannot be
   transferred so that all four checks hold — for example one mid-merge, mid-rebase or
   mid-cherry-pick — MUST be classified `needs_decision`.
5. The legacy entry's folder, branch, content and registration MUST NOT be removed or
   altered until the lossless verification of §3.4 has passed. When any step of a bring-over
   fails, `migrate-legacy` MUST remove the partial clone it made, MUST leave the legacy entry
   in exactly the state it was found in, and MUST report the entry as `needs_decision`
   naming the step that failed. Only after verification passes MUST the legacy entry be
   retired as in §3.1.

### 4. Stuck foreign-platform registrations are removed one by one

1. A **stuck registration** is a `.git/worktrees/<name>` admin entry that is locked with a
   reason containing "initializing" and whose recorded working folder is absent or holds no
   checkout. Each stuck registration MUST be removed individually, by removing that one
   admin entry, and MUST be reported in `retired` with reason `stuck_registration`.
2. A locked "initializing" entry whose working folder exists and holds a checkout is not a
   stuck registration; it MUST be classified under §2 like any other legacy entry.
3. Removing a stuck registration MUST leave every other ref, registration, folder and
   config value byte-identical.

### 5. One JSON answer, a no-change preview, no prompts, safe to rerun

1. `migrate-legacy` MUST answer with exactly one JSON object in the ADR-070 §3.5 result
   contract (BO-4300c-2), carrying the lists `retired`, `brought_over` and `needs_decision`.
   Each element MUST name the entry's path and branch; each `needs_decision` element MUST
   carry a reason; each `brought_over` element MUST name the new workspace's path.
2. `--preview` MUST produce the same answer, with the same three lists, while changing
   nothing on disk or in git. This refines ADR-070's Operational note: the cut-over chore
   there named `git worktree prune`; under this ADR the chore is
   `worktree.py migrate-legacy`, and blanket prune is forbidden (§1.4).
3. `migrate-legacy` MUST NOT read stdin and MUST NOT prompt. The human decision on a
   `needs_decision` entry is taken outside the run; every option the run needs arrives as
   an argument.
4. `migrate-legacy` MUST be idempotent. After a run, `git worktree list` of the main
   checkout MUST list only the main checkout and the `needs_decision` entries; a rerun with
   no other change MUST answer `ok` with empty `retired` and `brought_over` lists and the
   same `needs_decision` list.

### 6. Proof runs the deployed maker

1. Tests for this ADR MUST run the DEPLOYED maker as a separate process, resolved through
   the shared test locator delivered by BO-4300f-4, against real temporary git repositories
   with a real bare hub and real `git worktree` legacy entries, per ADR-070 §5.3. They MUST
   NOT import the maker, mock git, grep its source, fall back to the `templates/` copy, or
   spawn the package's own `build.py`; fixture projects MUST carry a minimal stub build
   entry point that installs a real, rejecting hook.
2. All fixture projects, hubs and workspaces MUST live under the test's temporary
   directory and run git with an isolated global and system config, so the developer's own
   branches, registered worktrees and local git config are unchanged afterwards.

## Consequences

### Positive

- **No unsent work is lost by the cut-over.** A legacy workspace is removed only when it
  holds nothing, or after a byte-level proof that everything it held exists in its
  replacement. The worst case for a holds-work entry is that it stays exactly where it was.
- **The `git worktree` exception is bounded.** One verb, one helper module, legacy entries
  only; any other `git worktree` call in the package is a defect against ADR-070 §1.4 and
  this ADR's §1.3.
- **Plan-then-act makes the preview truthful.** Because every outcome is decided before the
  first change, `--preview` and a real run produce the same three lists.
- **Brought-over workspaces are not second-class.** They come from `ensure`, so they carry a
  marker, a real install and firing hooks, and `locate`/`list` find them like any other.
- **The stuck WSL entries go away without collateral.** Targeted removal replaces a
  blanket prune that would also have swept every other stale entry.

### Negative

- **One unclassifiable entry blocks the whole cut-over.** §2.3 trades progress for safety:
  the operator must fix or hand-resolve that entry before any entry is retired.
- **Some recoverable workspaces land in `needs_decision`.** Mid-operation states, locked
  entries and anything §3.4 cannot verify are left for a person even when a careful human
  could have moved them, so the cut-over does not finish unattended in every repository.
- **Bringing over is expensive.** Each brought-over entry pays a full `ensure` (including
  the roughly 62 s install build ADR-070 accepts), plus a verification pass over every
  transferred file.
- **The verdict rule exists in two places until BO-4100c-1 ships.** Until the assessor is a
  deployed module, `migrate-legacy` carries its own implementation of the same definition,
  and the two can drift until §2.2's hand-over happens.
- **Branches are left behind.** Because the cut-over never deletes refs (§1.5), local
  branches of retired workspaces remain in the main checkout for a separate clean-up.

### Operational

- Run `worktree.py migrate-legacy --preview` first; read `needs_decision`; then run without
  `--preview`. A person resolves each `needs_decision` entry (push, discard, or bring over by
  hand) and reruns until the list is the set intentionally kept.
- The answer's error codes and the `migrate-legacy` arguments MUST be documented in
  `docs/reference/workspace-maker-answers-and-codes.md` and
  `docs/reference/workspace-maker-interface.md`.
- Setting `gc.auto=0` on the main checkout while legacy entries remain (ADR-018 migration
  step 2) is unchanged and outside this verb.
- After the cut-over has run in a repository, any newly appearing `git worktree` entry
  signals a path that bypassed the maker and is a defect to file, not a workspace to
  migrate again.

## Alternatives

- **A separate, free-standing migration script.** Rejected. It is a second door to
  workspace removal and creation, which ADR-070 §1.4 forbids, and as an unlisted file it
  would be missing from the deployed layout exactly when the cut-over is run.
- **Blanket `git worktree prune` plus `git worktree remove --force` on every entry.**
  Rejected. It deletes unsent commits, edits and untracked files without a trace, which the
  user's Q10 decision forbids, and prune also removes registrations unrelated to the target,
  breaking "nothing else changes".
- **Always bring over every holds-work entry, with no `needs_decision` outcome.** Rejected.
  Mid-merge and mid-rebase states, stashes and in-progress operations cannot always be
  transferred so that every SHA and byte is verifiably present; forcing the bring-over would
  turn an unverifiable copy into a silent loss once the legacy folder is removed.
- **Push unsent commits to the hub so they count as sent, then retire.** Rejected. It
  publishes unreviewed work on the shared project, changes the hub outside this verb's
  scope, and still does not preserve uncommitted or untracked content.
- **Ask the operator per entry with an interactive prompt.** Rejected. ADR-070 §3.6 forbids
  the maker from reading stdin; an unattended caller would stall indefinitely on the first
  ambiguous entry.
- **Report an unclassifiable entry as `needs_decision` and carry on.** Rejected. It folds
  "the maker could not tell" into "the maker looked and decided a person must choose", so a
  maker defect produces an `ok` answer that looks like a correct classification.
- **Leave legacy workspaces in place indefinitely beside the new clones.** Rejected. They
  keep sharing the main checkout's `.git` (the ADR-018 corruption and shared-hook class),
  stay invisible to `locate` and `list`, and leave the repository with two kinds of
  workspace — the state ADR-070 was written to end.

## References

- Originating ticket: `tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/55_TICKET-20260927-BO-4300f-3.md`
  (AC [BO-4300f-3](../../acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/BO-4300f-3.yaml);
  children BO-4300f-3-i, BO-4300f-3-ii).
- Related ACs: BO-4300a-1 (`ensure` and the marker format), BO-4100c-1 (holds-work verdict),
  BO-4300c-1-iii (build-output rule), BO-4300c-2 (result contract), BO-4300f-4 (shared test
  locator).
- [ADR-070 — One Workspace Maker and One Project-Root Resolver](ADR-070-single-workspace-maker-and-resolver.md).
- [ADR-018 — Agent Isolation Topology](ADR-018-agent-isolation-topology.md).
- [ADR-031 — Worktree Quality Gate Guard](ADR-031-worktree-quality-gate-guard.md).
- [Decision memo](../../analysis/2026-09-25-worktree-isolation-decision-memo.md),
  [consolidation analysis](../../analysis/2026-09-25-worktree-creation-consolidation.md),
  [migration plan](../../analysis/2026-09-25-worktree-migration-plan.md).
- [Worktree Manager component](../components/worktree-manager.md).
