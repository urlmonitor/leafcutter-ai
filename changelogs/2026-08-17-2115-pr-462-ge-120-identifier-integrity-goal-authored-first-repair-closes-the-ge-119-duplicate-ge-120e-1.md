---
title: "PR #462 — GE-122 identifier-integrity goal authored; first repair closes the GE-119 duplicate (GE-122e-1)"
date: "2026-08-17"
time: "21:15"
type: manual
components: 
  - ac_store
  - commit_guardian
  - ticket_lifecycle
summary: "Wrote the specification for making sure a work-item number always points to exactly one thing, and used it to fix a real case where two unrelated pieces of work had both been numbered GE-119."
description: "5 commits. Authored the GE-120 'numbers mean one thing' acceptance-criteria tree (28 records) specifying identifier-integrity guarding across four namespaces (AC ids, ticket ids, ADR numbers, diagram sequence numbers) at three enforcement stages (authoring-time, commit-time, CI). This is specification only — no guard is implemented yet; the motivating finding is that uniqueness is currently checked for zero of the four namespaces because every existing validator inspects one file at a time and structurally cannot see a duplicate across files. Shipped the tree's first repair (originally GE-120e-1): the identifier GE-119 had been claimed by two unrelated records, a 32-file goal tree and a parentless detail record about the contract-shrinking guard; the parentless record was renumbered to GE-111f and parented under GE-111, all 15 '# covers: GE-119' coverage tags were repointed across two test modules, the guard source citation was updated, and the 2026-08-14 changelog entry that referenced the old identifier gained a clarifying note rather than a rewritten citation (that file is otherwise untouched). The AC store now held 2,997 records with 2,997 distinct ids — zero duplicates — at the time this branch's PR #462 landed. RECONCILED 2026-08-18: while this branch was in flight, origin/main's PR #453 independently resolved the SAME GE-119 collision from the other side, renaming the 32-file goal tree itself from GE-119 to GE-120 — colliding head-on with this branch's own GE-120 'numbers mean one thing' tree. After merging origin/main, this tree (all 28 records) was renumbered to GE-122, and GE-122e-1's criteria were rewritten to describe the joint outcome: GE-119 is now retired and claimed by no record; the goal tree claims GE-120; the contract-shrinking record claims GE-111f exactly as this repair always intended. Also deleted a stale duplicate copy of EPIC-MoveOnMainOnly sitting in tickets/99_rejected/ (the canonical done copy remains in tickets/99_done/)."
pr: 462
adrs: 
  - ADR-029
commits: 
  - 9552bb593
  - 28d61f0f2
  - 16bb463c7
  - 4a83c8280
  - 6ade65d88
breaking: false
---

## Entry

**New specification, not yet built.** This change adds a new acceptance-criteria
tree, minted as GE-120 ("Trust that a number always refers to exactly one piece
of work"), 28 records that spell out how identifier collisions should be
prevented across four kinds of numbers used in this project — AC ids, ticket
ids, ADR numbers, and diagram sequence numbers — and at three points in time:
while someone is authoring a new one, at commit time, and in CI. Nothing here
implements that guard yet; it is the design for a future fix. The reason it
matters: none of the four namespaces are currently protected against
duplicates, because every existing check looks at one file at a time and
simply cannot notice that a number two files away was already taken.

**One repair from that tree already shipped (originally GE-120e-1).** The
identifier `GE-119` turned out to be in use by two completely unrelated pieces
of work — a large goal tree and a small, unparented note about a different
guard. The unrelated note was renumbered to `GE-111f` and given a proper home
under `GE-111`. All 15 places in the test suite that referenced the old number
were updated, along with the source citation in the affected guard, and the
dated changelog entry that used to cite the old number now carries a short
clarifying note rather than being rewritten.

**Reconciled after merging origin/main (2026-08-18).** While this branch's PR
#462 was in flight, a separate, concurrently-authored change on origin/main
(PR #453) independently resolved the SAME `GE-119` collision from the other
side: it renamed the 32-file goal tree itself from `GE-119` to `GE-120` —
which collided head-on with this branch's own `GE-120` "numbers mean one
thing" tree. Merging origin/main surfaced both renumberings at once. This
tree's own 28 records (and the ticket and test module that implement its
first repair) were renumbered again, to `GE-122`, and the repair AC's criteria
were rewritten to describe the joint outcome: `GE-119` is now a RETIRED
identifier claimed by no record and must never be reissued; the goal tree
claims `GE-120` with its 32 files unchanged; the contract-shrinking record
claims `GE-111f`, exactly as this repair always intended. The acceptance-
criteria store is, once again, fully unambiguous — every id resolves to
exactly one record.

**Also included:** removal of a leftover duplicate copy of the
`EPIC-MoveOnMainOnly` ticket tree that had been sitting in the rejected-tickets
folder alongside its real, completed copy.

**Also included (2026-08-18):** the architecture decision record governing
decision-number collisions was amended, along with the convention document that
restates it. Two things changed. First, its rule that the guard should stay
quiet and let the commit through on *any* unexpected error was too broad: it
covered the case where the guard could not read the numbers at all, which would
mean reporting "your number is fine" after checking nothing. The rule now turns
on whether the guard managed to read the sequence — a bug in the guard's own
reporting still lets your commit through, because a guard that blocks work
indiscriminately gets switched off, but a guard that could not see what it was
meant to check now says so and stops. Second, the record claimed the guard was
switched on in pre-commit. It is not, and never has been.

**Worth knowing:** three guard scripts are deployed but registered nowhere as an
official check, so none of them has ever run (`check_adr_collision.py`,
`check_ticket_state_integrity.py`, `check_ticket_no_branch_move.py`). Registering
them is part of the work this specification covers and is not done yet. The
practical consequence is that decision numbers, ticket states and ticket
locations have been unguarded throughout — clean by discipline rather than by
enforcement.
