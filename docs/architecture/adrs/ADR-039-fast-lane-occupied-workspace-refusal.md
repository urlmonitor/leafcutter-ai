---
title: "ADR-039: Fast-Lane Occupied-Workspace Refusal"
description: "When the fast lane's target workspace is already occupied the run MUST end in a named refusal rather than reuse the workspace, because silently building on another run's leftovers can destroy uncommitted work; this supersedes KI-BO-015's suggested reuse remedy while keeping its root-cause fix."
type: "adr"
status: "active"
created: "2026-09-07"
last_updated: "2026-09-07"
deciders:
  - BrainCandy
  - adr-author
components:
  - build_orchestration
  - worktree_manager
related_docs:
  - docs/architecture/components/build-orchestration.md
  - docs/how-to/fast-lane-build.md
  - docs/known-issues/build-orchestration.md
  - docs/architecture/adrs/ADR-035-fast-lane-closed-producer-roster.md
related_code:
  - templates/scripts/setup_ticket_worktree.py
  - scripts/setup_ticket_worktree.py
  - templates/workflows-js/fast-lane-ship.js
  - unit_tests/build_orchestration/test_bo2400f_13_occupied_workspace_refusal.py
---

# ADR-039: Fast-Lane Occupied-Workspace Refusal

## Status

| Field | Value |
|---|---|
| Status | Proposed |
| Date | 2026-09-07 |
| Author | adr-author, on the decision of BrainCandy (`BO-2400f-13`) |
| Supersedes | — (supersedes no ADR; supersedes the *fix direction* of `KI-BO-015`, which is a known-issue entry, not an ADR) |

This ADR is `Proposed`, not `Accepted`, on purpose. The implementation
`BO-2400f-13` specifies has not merged, and the decision has never run against a
live operator. The user's own framing was *"we will see how that will work once
implemented."* Promote to `Accepted` only after the refusal has been exercised
in a real run, not merely on the strength of a green test suite.

---

## Context

The fast lane's promise is narrow and specific: point it at an acceptance
criterion, get a pull request back. Its first phase opens a build workspace —
a git worktree at `worktrees/<slug>` on a branch `fast-lane/<slug>`, both
derived from the criterion's id alone (`BO-2400f-3`).

Two written sources in this repository specified **opposite** behaviour for what
should happen when that workspace is already occupied, and the conflict was not
noticed until the code was written.

### The first source: `KI-BO-015`

[`KI-BO-015`](../../known-issues/build-orchestration.md) records a real defect.
Its title, **as written when this collision occurred**, was: *"`_worktree_exists`
does not know the `fast-lane/` prefix, so a fast-lane run can never **reuse** its
own worktree and aborts at phase one."* That wording is quoted here because it is
the framing that caused the collision — it names the *remedy* (reuse) as though
it were the *defect*. The entry's title has since been corrected to *"cannot
**recognise** its own workspace"*, and the correction is the maintainer's own
acknowledgement of the point this ADR's §7 makes.

`_worktree_exists` matched a branch against three hardcoded prefixes
(`feature/`, `ticket/`, `ac-authoring/`); `fast-lane/` was absent, so the lookup
could never match a fast-lane worktree and the reuse branch was unreachable
code. Every invocation fell through to `git worktree add`, which fails with exit
128 the moment anything occupies the target path, and the lane surfaced that as
`{"worktree_path": ""}` — a shaped-but-empty success — and halted having done
nothing.

Among the harms `KI-BO-015` lists is **non-idempotency**: *"Re-running the fast
lane on an AC it has already built fails the same way, against its own prior
worktree — which is exactly what the reuse branch exists to prevent."* Its
implied remedy is therefore to make the reuse branch reachable — to let a re-run
step back into the workspace it left behind.

### The second source: `BO-2400f-13`

[`BO-2400f-13`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13.yaml)
and its four children `-13-i`…`-13-iv` require the opposite ending. The parent
criterion requires that *"the run's terminal outcome is a refusal: it is not
reported as a successful run, it does not report a blank or absent workspace
location, and it never asserts that a pull request was opened"*; that the
refusal *"names, in one message, both the acceptance criterion the operator
asked for and the occupied location"*; and that it *"states what the operator
can do next, and for each option says plainly whether taking it throws anything
away, so clearing empty residue and throwing away unsaved work are never offered
as the same gesture."*

The children carry the detail. `-13-i` requires that a refusal on the lane's
**own** leftover workspace report whether it holds uncommitted changes and
whether that earlier attempt opened a pull request — so the operator can tell
the residue of a finished run from the debris of a dead one — and that the lane
*"does not step back into that workspace, does not build in it, and does not
clear it on the operator's behalf, however empty it looks."* `-13-ii` requires
that a **foreign** occupant be named as foreign, never offered a
work-discarding option, and that an occupant which cannot be classified with
confidence be reported as foreign rather than as the lane's own. `-13-iii`
requires the refusal be inert: no claim taken, no release step reached, the
occupant untouched, no new branch or workspace left behind, and repeating the
refusal costs only the check. `-13-iv` requires that a genuinely free location
is never refused — an existing but **empty** directory is not an occupant,
because `git worktree add` succeeds into one — and that a workspace opened new
for this run be distinguishable from one carried over, naming the mainline
commit it was cut from.

### How the conflict surfaced

A `/fast-lane-build BO-2400f-13` run reached its `verify_green_and_coverage`
gate with **9 of 10** new tests passing. The single failure was
`test_other_worktree_lookup_call_sites_still_resolve_a_bare_slug`, which
asserted that a re-run must **reuse** an already-registered slug. The coder had
implemented the acceptance criterion's refusal; the test-writer had written a
guard from `KI-BO-015`'s framing. Neither was careless — each had faithfully
implemented a different one of the two written sources.

The gate caught the contradiction before anything shipped. The cost was roughly
**80 minutes and ~907k subagent tokens for no pull request** — which is the cost
of *not* having recorded this decision, and the reason it is being recorded now
rather than left as a code comment. A comment on the refusal branch would tell a
future reader what the code does; it would not tell them that the opposite
behaviour was also specified, in writing, by a document still open in the
known-issues register.

---

## Decision

### 1. An occupied workspace ends the run in a refusal

When the fast lane's first phase finds the workspace it resolves to for an
acceptance criterion already occupied, the run **MUST** end in a named refusal.
It **MUST NOT** reuse the workspace, **MUST NOT** build in it, **MUST NOT**
bring it up to date against the current mainline, and **MUST NOT** clear it on
the operator's behalf — however empty it looks.

### 2. Both occupancy conditions MUST be checked, before anything is created

`cmd_create_fastlane_worktree` in `templates/scripts/setup_ticket_worktree.py`
**MUST** check both conditions before creating a branch, a directory, or a
worktree:

- **(A) The path is occupied** — `worktrees/<slug>` exists *and* (it is not a
  directory, or it contains at least one entry). An existing **empty** directory
  is **NOT** an occupant: `git worktree add` succeeds into one, and treating it
  as an occupant would false-refuse on stale residue, violating `BO-2400f-13-iv`.
- **(B) The branch is checked out elsewhere** — `fast-lane/<slug>` is registered
  to some worktree at any path. This **MUST** be checked even when the path is
  free, because `git worktree add` on an already-checked-out branch exits 128.

A refusing run **MUST** leave no branch, no directory and no worktree behind.

### 3. The refusal is a discriminated payload that cannot be mistaken for success

The workspace command **MUST** print a single JSON line discriminated by an
`outcome` field whose value is `opened` or `refused`. On `refused` the
`worktree_path` key **MUST be absent** — not blank, not null. The lane's Phase 1
guard in `templates/workflows-js/fast-lane-ship.js` **MUST** branch on
`outcome === "opened"` and on nothing else, and that guard **MUST** sit ahead of
the existing empty-path check.

The read **MUST** fail closed by a plain-falsy test: a missing `outcome`, a
null, an unparseable reply, or a legacy `{"worktree_path": ""}` from a stale
deployed copy all take the refusing branch and report
`reason: occupancy_undetermined`. There **MUST** be no `|| true` and no
`?? "opened"`.

### 4. The refusal MUST be legible to the operator and MUST NOT relay git's voice

The refusal message **MUST** name both the acceptance criterion and the occupied
location in one sentence. Every entry in `refusal.options` **MUST** carry an
explicit boolean `destructive`, so that clearing empty residue and throwing away
unsaved work are never presented as the same gesture. The strings `fatal:`,
`is already used by worktree at`, and `contains modified or untracked files, use
--force to delete it` **MUST NOT** reach the operator, and the process **MUST
NOT** surface a raw exit 128.

An occupant that cannot be classified with confidence **MUST** be reported as
`foreign`, never as the lane's own — there is deliberately no `unknown` value —
so an unrecognised occupant is never handed the option that discards work.

### 5. The workspace location MUST stay derived from the criterion's identity alone

The path and branch **MUST** continue to be derived from the acceptance
criterion's id with no per-run discriminator, so two runs on one criterion
resolve to the same place and the second refuses. Concurrency on a single
criterion is settled by the claim rules (`BO-2400f-8`), not by inventing a
second directory. This diverges deliberately from the sibling authoring lane
(`BO-1500f-2`), which mints a per-run workspace; the divergence is recorded here
because the two will otherwise read as inconsistent.

### 6. Where an acceptance criterion and a known-issue entry conflict, the AC governs

An acceptance criterion is the specification. A known-issue entry records an
observation and a suggested direction. When the two disagree about behaviour,
the acceptance criterion **MUST** be implemented and the known-issue entry's fix
direction **MUST** be treated as superseded. This rule is stated generally
because the collision that produced this ADR will recur: the known-issues
register is written at the moment of discovery, when only the symptom is
understood, and the AC store is written later with the whole problem in view.

### 7. `KI-BO-015`'s root cause is fixed; only its remedy is superseded

This point is the one most likely to be misread, so it is stated precisely.

The defect `KI-BO-015` identified — that `_worktree_exists` was blind to the
`fast-lane/` prefix — is **genuinely repaired**. `refs/heads/fast-lane/{branch}`
is now recognised by the lookup, and the lookup's verdict is now actually
consumed by `cmd_create_fastlane_worktree`. `KI-BO-015` was correct about the
mechanism, correct about the evidence, and correct that the lane was structurally
incapable of noticing its own prior workspace.

What is superseded is only the **conclusion drawn from that repair**:
`KI-BO-015` assumed that once the lookup could see the workspace, the right
thing to do was reuse it. This ADR decides that once the lookup can see the
workspace, the right thing to do is refuse and say so. The prefix fix is a
precondition for both endings; it is not itself in dispute.

Any signature change to `_worktree_exists` **MUST** be accompanied by an audit of
all four call sites (`cmd_setup_ticket`, `cmd_create_only`,
`cmd_create_ac_worktree`, `cmd_create_fastlane_worktree`) in the same commit; the
three bare-slug callers **MUST** keep resolving from a bare slug. The change
**MUST** land in `templates/scripts/setup_ticket_worktree.py` and be mirrored to
`scripts/setup_ticket_worktree.py` by running `build.py` — the deployed copy is
what the lane actually invokes, and the two are not byte-identical by design.

---

## Consequences

### Positive

- **Uncommitted work in a leftover workspace cannot be silently destroyed or
  silently built upon.** Losing work this way has happened in this repository;
  the refusal removes the mechanism.
- **The operator is told which of two very different situations they are in.**
  `-13-i` (own prior attempt, with its uncommitted-changes and pull-request
  facts) and `-13-ii` (foreign occupant) are distinguishable from the message
  alone, because the right next move differs between them.
- **A run that cannot proceed says so instead of reporting a hollow success.**
  The `{"worktree_path": ""}` shape — a present field with a blank value that
  the lane read as success — becomes structurally inexpressible.
- **The refusal is inert and repeatable.** No claim is taken, the store is
  untouched, the occupant is untouched, and refusing twice costs only the check.
- **A green fast-lane result now has a knowable baseline.** `-13-iv` requires the
  proceeding run to report that its workspace is new and name the mainline commit
  it was cut from, so a green result can be attributed to a specific mainline.

### Negative

**Every re-run against the same acceptance criterion now requires an operator
decision.** This is the accepted cost and it is not small. For a tool whose
entire promise is *"point at an AC, get a PR back"*, inserting a human into the
loop on every retry is real friction — and retrying is not an edge case, it is
what an operator does after a failed run. This is the single most likely reason
someone will later want to reverse this decision, and they will have a
reasonable case.

Two further costs:

- **A refusal is indistinguishable from an outage to an unattended caller.** Any
  automation that drives the lane without a human present will stall on a
  leftover workspace rather than recover from it.
- **Leftover workspaces accumulate.** Because the lane never clears its own
  residue, `worktrees/` grows with the debris of dead runs until someone prunes
  it by hand. `KI-BO-015` already records live examples
  (`worktrees/bo-2900g-3`).

### Operational

- The occupancy check runs before the connected-set resolution, so a refusal
  costs one check rather than the multi-minute store traversal recorded in
  `KI-BO-014`.
- `KI-BO-015` has been marked **RESOLVED** — root cause fixed, proposed remedy
  deliberately not taken — and now cites this ADR. Its title was corrected in the
  same pass, from *"can never reuse"* to *"cannot recognise"*, because the old
  wording stated the remedy as if it were the defect. The entry is **retained,
  not deleted**, since acceptance criteria and commit messages cite it by id.
  This is the register's exception to its own delete-on-fix policy.
- Covering tests **MUST** execute: either the lane under
  `run_workflow_under_e2` asserting on recorded dispatches, or the workspace
  command as a real subprocess against a real temporary repository. A test that
  greps either file for a prefix, a message, or a statement order is not
  acceptable evidence — it passes unchanged on dead code, which is the exact
  defect being fixed.

### What would justify revisiting this

Recorded now, while the reasoning is fresh, so a future reader does not have to
reconstruct it:

- **If operators overwhelmingly choose `clear_and_rerun`**, the refusal is asking
  a question with only one real answer, and an auto-clear for the
  provably-clean-and-unpushed case is warranted. This is the strongest signal and
  the most likely outcome.
- **If refusals cluster on foreign occupants rather than the lane's own
  residue**, the problem is workspace-path allocation, not re-run semantics, and
  the location-derivation rule (§5) is what should be revisited instead.
- **If an unattended driver becomes a real use case**, a non-interactive policy
  flag will be needed, and its default should be re-argued rather than assumed.

The door to the first of these is deliberately left open: the refusal payload
`BO-2400f-13` specifies already computes exactly the facts an auto-clear would
need — `uncommitted_changes`, `published.pushed`, and `published.pr_url`. That
was not incidental.

---

## Alternatives

- **Silent reuse of the existing workspace** — the remedy `KI-BO-015` implies.
  Rejected. It cannot distinguish a clean leftover from an in-flight run, so it
  would build on top of, and eventually commit or discard, another run's
  uncommitted work. It also breaks `BO-2400f-3`'s promise that the workspace is
  cut from the latest `origin/main`: an earlier attempt's workspace is pinned to
  whatever mainline existed when that attempt started, so a green result would be
  measured against a mainline that no longer exists, and any uncommitted debris
  would ride into the pull request diff.

- **Auto-clear the workspace when it is provably clean and its work already
  landed** — a genuine middle path, and the most likely future revision. It
  preserves the safety property (nothing unsaved is discarded) while removing the
  friction in the common case. Rejected **for now**, not on principle: "provably
  clean and unpushed" is a compound judgement built on `uncommitted_changes`,
  `published.pushed` and `published.pr_url`, each of which can be
  *undetermined*, and no evidence yet exists about how often those come back
  null in practice. Shipping an auto-clear whose cleanliness proof silently
  degrades to a guess would reintroduce exactly the work-loss mode this ADR
  exists to close. The Product Owner deferred it explicitly as a possible future
  criterion; §"What would justify revisiting this" names the evidence that would
  promote it.

- **Auto-suffix the workspace path so a second run gets its own directory** —
  e.g. `worktrees/<slug>-2` or a timestamped path. Rejected. `BO-2400f-13`'s
  second Given requires the location be derived from the criterion's identity
  alone, so two runs on one criterion resolve to the same place; that identity
  is what makes the collision detectable at all, and parallel lanes rely on it
  as an exclusion property. It also does not work: verified live on 2026-08-25
  in a throwaway repository, `git worktree add <newpath> fast-lane/probe` while
  that branch is checked out elsewhere exits 128 with
  `fatal: 'fast-lane/probe' is already used by worktree at '<path>'`. A distinct
  directory does not buy a distinct branch, so the second run would fail anyway —
  just later, and with git's voice instead of ours.

---

## References

- [`BO-2400f-13`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13.yaml)
  — the governing acceptance criterion, with children
  [`-13-i`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13-i.yaml),
  [`-13-ii`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13-ii.yaml),
  [`-13-iii`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13-iii.yaml),
  [`-13-iv`](../../acceptance-criteria/build-orchestration/BO-2400-fast-lane-build/BO-2400f-13-iv.yaml).
- [`KI-BO-015`](../../known-issues/build-orchestration.md) — the known-issue entry
  whose root cause is fixed and whose fix direction this ADR supersedes.
- [`KI-BO-014`](../../known-issues/build-orchestration.md) — why the occupancy
  check must precede connected-set resolution.
- [ADR-035 — Fast-Lane Closed Producer Roster](ADR-035-fast-lane-closed-producer-roster.md)
  — the sibling fast-lane decision.
- [How to run a fast-lane build](../../how-to/fast-lane-build.md)
- [Build orchestration component](../components/build-orchestration.md)
