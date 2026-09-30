---
title: "KI-ACD-20260921-1615 — An AC's `expects_from` edge is dropped from the generated ticket whenever that same AC's `delivers_to` is null, so terminal leaves lose their dependencies"
description: "high — build order is wrong at the end of every contract chain, and the ticket still renders the contract in prose so it reads as correct"
type: reference
category: reference
status: active
created: '2026-09-21'
last_updated: '2026-09-21'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACD-20260921-1615 — `expects_from` is never a source for a generated ticket's `depends_on`, so a contract edge survives only if its author also duplicated it into `depends_on` by hand

- **Severity:** high — a dropped edge means a batch drive builds a consumer before its
  producer; the ticket renders the contract in prose, so the omission looks like an
  absence of dependency rather than a loss of one
- **Status:** FIXED on branch `feature/acd-generator-edges` (see Resolution). Left open
  until that branch merges.
- **Occurrences:** 1 (2026-09-21, BO-4100d — 2 of 3 edges lost)
- **First seen:** 2026-09-21 · **Last seen:** 2026-09-21
- **Where:** `scripts/ac_store/_gtfa_store.py::_build_ticket_depends_on`

> **This entry was first filed with the wrong mechanism and corrected the same day.**
> The original diagnosis claimed the edge was dropped when the consuming AC's
> `delivers_to` was null. That was a coincidence across four inconsistently-authored
> records, not a cause — disproved by calling `_build_ticket_depends_on` with
> `delivers_to: None` and an explicit `depends_on` present, which resolved correctly.
> The corrected mechanism is below. The original table is kept because the observations
> in it are real; only the explanation was wrong.

## Symptom

`depends_on` on a generated ticket appeared to be derived from the AC's `expects_from`,
but only sometimes. Observed across four records generated in one pass:

| AC | AC's own `depends_on` | `expects_from` | ticket `depends_on` |
|---|---|---|---|
| `BO-4100d-1` | `[BO-4100d]` (parent) | — | `[]` — correct |
| `BO-4100d-2` | `[BO-4100d]` (parent) | `BO-4100d-1` | `[]` — **dropped** |
| `BO-4100d-3` | `[BO-4100d, BO-4100d-1]` | `BO-4100d-1` | `[TICKET-…d-1.md]` — resolved |
| `BO-4100d-3-i` | `[BO-4100d-3]` (parent) | `BO-4100d-3` | `[]` — **dropped** |

## The actual mechanism

`_build_ticket_depends_on` read **only** `ac.get("depends_on")`. It never consulted
`expects_from` at all — there was no derivation to be inconsistent about.

Every row above follows from that one fact plus the pre-existing structural-parent drop:

- **`d-3` resolved** not because of any contract handling, but because its author had
  *redundantly duplicated* the contract target into `depends_on` alongside the parent.
  The generator was reading that literal entry.
- **`d-2` dropped** because its `depends_on` held only its structural parent, which is
  deliberately dropped, and its `expects_from` was never read.
- **`d-3-i` dropped** for the same reason: its sole `depends_on` entry
  (`BO-4100d-3`) *is* its structural parent.

So the contract layer and the ordering layer were simply not connected. An
`expects_from` edge reached the generated ticket only when a human had written the same
fact twice, in two different fields, in two different vocabularies.

This is the generator-side counterpart of **KI-ACD-015** ("Epic ordering reads
`depends_on` only, so `expects_from` contract edges are invisible to the build
sequencer"). Same disconnect, one layer earlier: there the sequencer ignores the contract
edges, here the generator never writes them down in the first place.

## Resolution

Fixed on `feature/acd-generator-edges`: `_build_ticket_depends_on` now unions the AC's
`depends_on` with the ac_ids harvested from `expects_from` (order-preserving,
de-duplicated) before classification. The structural-parent drop and the dangling-id
warning are unchanged, so `d-3-i`'s parent edge is still correctly dropped — verified by
a test that passes both before and after, to prove the fix did not widen into
KI-ACD-021's territory.

Regression test: `unit_tests/ac_store/test_ki_acd_20260921_depends_on_expects_from.py`,
confirmed red before the fix (`Got depends_on=[]`) and green after.

## Why it reads as correct

The generated ticket still renders the contract in its `## Agent Contracts` → `### Expects
From` section, naming the producing AC and quoting the contract text. So a human reading
the ticket sees the dependency stated plainly, while the machine-readable `depends_on: []`
says there is none. Only a reader who compares the two notices.

## Consequence

A batch drive that orders work from `depends_on` will build `d-2` before `d-1`, and
`d-3-i` before `d-3`. In this instance `d-2` consumes the declared supported-kind set that
`d-1` establishes, so building it first means implementing against a contract that does
not exist yet.

## Reproduction

1. Author two leaf ACs, both with `expects_from` naming the same producer AC.
2. Give one of them a non-null `delivers_to` and leave the other `null`.
3. Generate a ticket from each.
4. Compare the `depends_on` frontmatter. The `delivers_to: null` one is empty; both
   tickets render the contract identically in the prose section below.

## Worked around, not fixed

The two dropped edges were set by hand on the BO-4100d tickets
(`e89f8150`). The generator is unchanged.
