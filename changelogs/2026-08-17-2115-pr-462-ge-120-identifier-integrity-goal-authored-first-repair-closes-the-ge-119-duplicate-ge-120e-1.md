---
title: "PR #462 — GE-120 identifier-integrity goal authored; first repair closes the GE-119 duplicate (GE-120e-1)"
date: "2026-08-17"
time: "21:15"
type: manual
components: 
  - ac_store
  - commit_guardian
  - ticket_lifecycle
summary: "Wrote the specification for making sure a work-item number always points to exactly one thing, and used it to fix a real case where two unrelated pieces of work had both been numbered GE-119."
description: "5 commits. Authored the GE-120 'numbers mean one thing' acceptance-criteria tree (28 records) specifying identifier-integrity guarding across four namespaces (AC ids, ticket ids, ADR numbers, diagram sequence numbers) at three enforcement stages (authoring-time, commit-time, CI). This is specification only — no guard is implemented yet; the motivating finding is that uniqueness is currently checked for zero of the four namespaces because every existing validator inspects one file at a time and structurally cannot see a duplicate across files. Shipped the tree's first repair (GE-120e-1): the identifier GE-119 had been claimed by two unrelated records, a 32-file goal tree and a parentless detail record about the contract-shrinking guard; the parentless record was renumbered to GE-111f and parented under GE-111, all 15 '# covers: GE-119' coverage tags were repointed across two test modules, the guard source citation was updated, and the 2026-08-14 changelog entry that referenced the old identifier gained a clarifying note rather than a rewritten citation (that file is otherwise untouched). The AC store now holds 2,997 records with 2,997 distinct ids — zero duplicates. Also deleted a stale duplicate copy of EPIC-MoveOnMainOnly sitting in tickets/99_rejected/ (the canonical done copy remains in tickets/99_done/)."
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
tree, GE-120 ("Trust that a number always refers to exactly one piece of work"),
28 records that spell out how identifier collisions should be prevented across
four kinds of numbers used in this project — AC ids, ticket ids, ADR numbers,
and diagram sequence numbers — and at three points in time: while someone is
authoring a new one, at commit time, and in CI. Nothing here implements that
guard yet; it is the design for a future fix. The reason it matters: none of
the four namespaces are currently protected against duplicates, because every
existing check looks at one file at a time and simply cannot notice that a
number two files away was already taken.

**One repair from that tree already shipped (GE-120e-1).** The identifier
`GE-119` turned out to be in use by two completely unrelated pieces of work —
a large goal tree and a small, unparented note about a different guard. The
unrelated note was renumbered to `GE-111f` and given a proper home under
`GE-111`; the goal tree keeps `GE-119` and is untouched. All 15 places in the
test suite that referenced the old number were updated, along with the source
citation in the affected guard, and the dated changelog entry that used to cite
the old number now carries a short clarifying note rather than being rewritten.
As a result, the acceptance-criteria store's 2,997 records now have 2,997
distinct ids — no duplicates, for the first time.

**Also included:** removal of a leftover duplicate copy of the
`EPIC-MoveOnMainOnly` ticket tree that had been sitting in the rejected-tickets
folder alongside its real, completed copy.

**Worth knowing:** while investigating this, three guard scripts were found
running in the pipeline but never registered anywhere as an official check
(`check_adr_collision.py`, `check_ticket_state_integrity.py`,
`check_ticket_no_branch_move.py`), and the architecture decision record for one
of them currently describes it as wired into pre-commit when it isn't wired in
at all. Those gaps are documented, not yet fixed.
