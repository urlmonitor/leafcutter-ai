---
title: "ADR-051: The Developer-Repo Guard Holds a Session-Exclusive Lock Instead of Narrowing Its Diff"
description: "The workspace proof suite's developer-repo guard takes an advisory, cross-platform, session-scoped lock on the developer repository for the whole snapshot-to-compare window. It keeps an unfiltered global snapshot, because filtering the diff to tell the suite's own leaks apart from concurrent sessions would weaken BO-4300f-4-i's 'any difference fails the session' contract."
type: "adr"
status: "active"
created: "2026-09-28"
last_updated: "2026-10-21"
deciders:
  - adr-author
  - architect-review
components:
  - testing_quality
  - worktree_manager
related_docs:
  - docs/architecture/adrs/ADR-018-agent-isolation-topology.md
  - docs/architecture/adrs/worktree-maker-amendment-1-2026-09-27.md
  - docs/architecture/components/worktree-manager.md
  - docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces
related_code:
  - unit_tests/build_orchestration/_developer_repo_guard.py
  - unit_tests/build_orchestration/conftest.py
  - unit_tests/build_orchestration/_workspace_maker_fixtures.py
  - unit_tests/build_orchestration/test_bo_4300f_4_i.py
  - unit_tests/build_orchestration/test_bo_4300f_4_i_reentrant_guard.py
---

# ADR-051: The Developer-Repo Guard Holds a Session-Exclusive Lock Instead of Narrowing Its Diff

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-28 |
| Author | adr-author, on the `architect-review` escalation recorded in [`02_TICKET-20260928-BO-4300-deployed-maker-test-support.md`](../../../tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02_TICKET-20260928-BO-4300-deployed-maker-test-support.md) (ACs `BO-4300f-4-i`, `BO-4300f-4`) |
| Supersedes | — |

## Context

The workspace proof suite (`unit_tests/build_orchestration/`) proves the one workspace maker
defined by [ADR-018 Amendment 1](worktree-maker-amendment-1-2026-09-27.md). Those proofs run
real `git` against real temporary projects. The suite starts from inside the developer's own
repository, so a buggy fixture could register a worktree, create a branch, or write a local
config value in the developer's repository instead of in its temp project.

AC `BO-4300f-4-i` ("Running the proof leaves the developer's own project unchanged") closes
that gap. Its technical requirement says that a session-level guard snapshots the developer
repository before the suite runs and compares after. The snapshot covers
`git worktree list --porcelain`, `git for-each-ref` and `git config --local --list`. The
requirement ends: **"any difference fails the session."**

In the first attempt at epic `EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace`, the guard lived
at `scripts/build_orchestration/developer_repo_guard.py`. It raised `DeveloperRepoChangedError`
at random because other agent sessions changed the same shared developer repository while the
suite was running. Ticket 43's and ticket 04's test-writers both reported this. Those changes
were real differences that the suite did not cause. The guard could not tell them apart from
a real leak, so the failures could not be diagnosed and were ignored. A guard that people
learn to ignore protects nothing.

There were two ways to fix this. One is to make the comparison smarter so that it ignores
changes the suite did not make. The other is to stop anything else from changing the
repository while the comparison window is open. This ADR records which one was chosen.
Every later BO-4300 proof ticket inherits the guard through ticket 02's shared fixtures, so
the choice binds the whole proof family, not one test file.

## Decision

1. **The guard MUST hold a session-exclusive advisory lock on the developer repository.**
   The session-scoped autouse fixture in `unit_tests/build_orchestration/conftest.py`, backed
   by `unit_tests/build_orchestration/_developer_repo_guard.py`, MUST acquire the lock before
   it takes the "before" snapshot. It MUST hold the lock until after the "after" comparison.
   The lock file MUST be a fixed path inside the developer repository's git directory:
   `<git-common-dir>/bo4300-proof-suite.lock`, where the directory comes from
   `git rev-parse --git-common-dir`. Using the common directory means that invocations from
   linked worktrees of the same repository contend on the same file.

2. **The lock MUST be a real OS advisory lock, not a create-exclusive spin.** On Windows the
   guard MUST use `msvcrt.locking`. On POSIX it MUST use `fcntl.flock`. A lock built from
   `os.open(..., O_CREAT | O_EXCL)` with retry MUST NOT be used, because a crashed session
   leaves the file behind and blocks every later run. An OS advisory lock is released by the
   kernel when the process exits.

3. **A second suite invocation MUST block on the lock and MUST NOT race the snapshot.** If a
   second invocation targets the same developer repository while the lock is held, it MUST
   wait for the lock. It MUST wait for at most a bounded timeout. The timeout MUST be
   configurable through the environment variable `BO4300_GUARD_LOCK_TIMEOUT_S`, which
   defaults to 600 seconds.

4. **A lock timeout MUST raise its own named error.** When the lock is not acquired within
   the timeout, the guard MUST raise `DeveloperRepoLockTimeoutError`. The message MUST name
   the lock path and the timeout that elapsed. This error MUST NOT subclass or be reported as
   `DeveloperRepoChangedError`. A timeout MUST NOT count as a pass, and it MUST NOT be
   converted into a skip. A stuck run and a real leak are different failures and MUST stay
   separately diagnosable.

5. **The snapshot MUST stay global and unfiltered.** Both the "before" and "after" snapshots
   MUST capture the full, unfiltered output of `git worktree list --porcelain`,
   `git for-each-ref` and `git config --local --list` for the developer repository. The guard
   MUST NOT filter entries by path prefix, ref namespace, temp-root match or config-key
   allow-list. After the snapshots are normalised by sorting lines, any difference MUST raise
   `DeveloperRepoChangedError` and fail the session. This keeps the AC's words "any
   difference fails the session" literally true.

6. **Fixture git MUST stay isolated from the developer's identity and config.** Every fixture
   `git` process MUST run with an isolated `HOME`, with `GIT_CONFIG_GLOBAL` pointed at a
   suite-owned file, and with `GIT_CONFIG_NOSYSTEM=1`, as the AC's technical requirement
   states. The guard's own snapshot commands MUST run without those overrides against the
   real developer repository, because that repository is what the guard measures.

7. **The guard MUST live in test support, not under `scripts/`.** The guard module MUST be
   `unit_tests/build_orchestration/_developer_repo_guard.py`. It MUST NOT be placed under
   `scripts/` or `templates/scripts/`. In the first attempt, an untracked guard under
   `scripts/` tripped the tracked-source guard in `scripts/build.py` for every other ticket's
   proof run.

8. **The guard MUST be re-entrant for the sessions it starts itself** (added 2026-10-21,
   approved by the user as "Approve re-entrant guard"). A test that runs a nested
   `python -m pytest` on files in this directory deadlocked on the lock its own parent held:
   `test_bo4500a_5_v` waited 600 s and then hit its 540 s subprocess timeout. The holder
   now names its lock file in the `BO4300_GUARD_HELD_LOCK` environment variable, which its
   child processes inherit. A session that finds the lock already taken, and whose inherited
   marker names that same lock file, skips the lock and its own snapshot, because the
   holder's before and after snapshots bracket the whole nested run. Decision 5 therefore
   still holds: a change made by the nested run fails the outer session. A marker that names
   a different lock file never matches. A stale marker, whose lock is free, is ignored,
   because the marker is consulted only after the lock is found taken.

## Consequences

### Positive

- The requirement "any difference fails the session" stays exactly as written. While the lock
  is held, no other proof-suite session can change the developer repository, so nothing
  legitimate remains to filter out and every difference counts as a finding.
- Random `DeveloperRepoChangedError` failures from parallel proof-suite runs disappear. A
  guard failure once again means the suite leaked.
- Timeouts and leaks produce separate named errors, so a stuck concurrent session is
  diagnosed as a stuck session. It is not hidden as a leak, and it does not hide a leak.
- An OS advisory lock is released automatically when a process dies, so a crashed run never
  leaves a lock that needs manual cleanup.

### Negative

- Proof-suite runs against the same developer repository are now serialised. Parallel agent
  sessions that each run the full BO-4300 proof suite wait for each other, which adds
  wall-clock time on busy days.
- The lock excludes only sessions that go through this guard. An agent session that changes
  the developer repository in some other way, such as a plain `git branch` or a
  `git worktree add` from a different workflow, can still land during the window. The guard
  will report that change as a difference. This is deliberate, because the guard cannot prove
  the change was not the suite's, but it can still produce a failure that is not the suite's
  fault. The failure message MUST show the diff so that a human can attribute it.
- The locking code has a Windows branch and a POSIX branch. Both need their own tests, and
  CI covers only one platform per job.

### Operational

- An operator who sees `DeveloperRepoLockTimeoutError` should look for another running
  proof-suite session, or a hung one, against the same repository. They should wait for it or
  kill it, and should not delete the lock file. Raising `BO4300_GUARD_LOCK_TIMEOUT_S` is the
  supported way to allow for long queues.
- An operator who sees `DeveloperRepoChangedError` should first check whether an agent session
  outside the proof suite changed the repository during the run, as described under Negative,
  before they treat the error as a suite leak.
- Every later BO-4300 proof ticket gets this guard automatically through the conftest in
  `unit_tests/build_orchestration/`. Later tickets MUST NOT add their own guard or their own
  developer-repo snapshot.

## Alternatives

- **Filter the diff to the suite's own temp roots.** Rejected. This approach ignores worktree
  entries, refs and config values that do not point into the suite's temp directories. It
  lets through exactly the leak class the AC exists to catch whenever the leaked entry does
  not happen to name a temp path, such as a branch created under a fixed name or a config key
  written without a path. It also silently narrows "any difference fails the session" into
  "any difference we recognise fails the session."
- **Run the suite against an isolated clone of the developer repository.** Rejected. AC-1's
  Given clause is "the developer's own project", and the proof must run "from inside that
  project". A synthetic clone is not that project, so a pass against a clone proves nothing
  about the repository the AC protects.
- **Retry the comparison, or treat a difference as flaky and re-snapshot.** Rejected. A leak
  that the suite causes is permanent, so a retry never helps with a real leak. A retry only
  helps when a concurrent change is reverted within the retry window. It turns a
  deterministic check into a timing-dependent one and still reports concurrent changes that
  persist.
- **A create-exclusive lock file (`O_CREAT | O_EXCL`) with a spin loop.** Rejected. A run that
  crashes or is killed leaves the file behind, and every later session then blocks until
  someone deletes it by hand. An OS advisory lock does not have this failure, because the
  kernel releases it when the process exits.
- **Fold a lock timeout into `DeveloperRepoChangedError`.** Rejected. A timeout means "could
  not measure" and a leak means "measured a change". Merging the two would let a stuck
  concurrent session look like a leak, or let a leak be dismissed as "just contention".

## References

- Originating ticket: [`02_TICKET-20260928-BO-4300-deployed-maker-test-support.md`](../../../tickets/00_inbox/epics/EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace/02_TICKET-20260928-BO-4300-deployed-maker-test-support.md), section "Architect-review decision (2026-09-28)".
- AC store: `docs/acceptance-criteria/build-orchestration/BO-4300-one-way-workspaces/` (`BO-4300f-4-i`, `BO-4300f-4`).
- [ADR-018 — Agent Isolation Topology](ADR-018-agent-isolation-topology.md) and its [Amendment 1](worktree-maker-amendment-1-2026-09-27.md). A1.6 requires tests to exercise the deployed maker. The guard protects the developer repository while those tests run.
- Numbering note: the architect-review comment suggested ADR-050. That number is already reserved in the `files_touched` of ticket 10 (`ADR-050-shell-runner-single-shell-executor.md`), so this record takes ADR-051, the next number that `scripts/adr_refs.py` reports as unclaimed.
