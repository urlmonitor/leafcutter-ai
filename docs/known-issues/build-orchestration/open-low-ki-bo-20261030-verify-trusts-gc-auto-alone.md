---
title: "KI-BO-20261030-verify-trusts-gc-auto-alone — workspace readiness checks gc.auto 0 but not maintenance.auto false, the setting that actually blocks automatic housekeeping on git 2.54+"
description: "medium — worktree_readiness.py's gc_auto_disabled check passes on gc.auto == 0 alone. Since git 2.54 porcelain auto-maintenance uses the geometric strategy, which ignores gc.auto; since 2.55 gc.auto <= 0 gates it only while maintenance.auto is unset. A workspace with maintenance.auto re-enabled passes verify but is not protected from geometric repack, reflog-expire or worktree-prune. Found 2026-10-30 while fixing the git 2.56 CI failure."
type: reference
category: reference
status: active
created: '2026-10-30'
last_updated: '2026-10-30'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20261030-verify-trusts-gc-auto-alone — readiness trusts the weaker of the two housekeeping settings

> Filed 2026-10-30 while fixing main's red CI after the runner moved to git 2.56
> (TICKET-20261030-HousekeepingTestTriggersOnGit256). Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** medium. Nothing is unprotected today, because `ensure` and the cut-over both set
  `maintenance.auto false`. But `verify` would accept a workspace that lost that setting.
- **Status:** open, no AC. A requirement is needed; draft below.
- **Occurrences:** 1 · **First seen:** 2026-10-30 · **Last seen:** 2026-10-30
- **Where:** `templates/scripts/worktree_readiness.py` about L240 (`gc_auto_disabled`, checks only
  `gc.auto == "0"`). The writers are `templates/scripts/worktree.py` about L110-111 and
  `templates/scripts/worktree_migrate.py` `_HELD` about L49.

## What the research found (git release notes and sources)

- **git 2.54:** `git maintenance` uses the `geometric` strategy by default. Porcelain (`commit`, `merge`, `am`,
  `rebase`, `fetch`, `receive-pack`) runs `git maintenance run --auto`, which no longer includes the gc task, so
  `gc.auto` no longer governs it.
- **git 2.55:** since 29364f1624, `gc.auto <= 0` turns auto-maintenance off, but only while `maintenance.auto` is unset.
- **git 2.56:** the geometric-repack threshold rose from 100 to 6700.
- **Effect:** on 2.56, `maintenance.auto false` stops every porcelain-triggered run before any task starts.
  `gc.auto 0` alone does not, if `maintenance.auto` is true. A local probe, simulating the 2.56 thresholds
  on git 2.52, confirmed both halves.
- **Not covered by either setting:** a direct `git maintenance run --auto` or `git gc --auto` call, a
  registered maintenance schedule, or a manual `git gc`.

## Draft requirement

> While a legacy workspace remains (the cut-over), and in every workspace the maker readies, the maker
> treats automatic housekeeping as disabled only when `maintenance.auto` is `false` at repository scope.
> `gc.auto 0` alone does not count as proof. `verify` refuses a workspace whose `maintenance.auto` is
> not `false`, as it already does for `gc.auto`.

Optional hardening (a user decision): also hold `maintenance.strategy none` during the cut-over. That
also neutralises direct `git maintenance run --auto` callers and a registered schedule.

## Related stale text

- ADR-018 about L70-71 says an ordinary `git commit` triggers auto-gc at about 6700 loose objects. Since
  git 2.54 it triggers geometric maintenance instead.
- `docs/known-issues/testing-quality/open-low-ki-tq-013.md` about L72-73 recommends `gc.auto=0` alone.
