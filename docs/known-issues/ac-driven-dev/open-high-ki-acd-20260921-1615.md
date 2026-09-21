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

# KI-ACD-20260921-1615 — An AC's `expects_from` edge is dropped from the generated ticket whenever that same AC's `delivers_to` is null, so terminal leaves lose their dependencies

- **Severity:** high — a dropped edge means a batch drive builds a consumer before its
  producer; the ticket renders the contract in prose, so the omission looks like an
  absence of dependency rather than a loss of one
- **Status:** open
- **Occurrences:** 1 (2026-09-21, BO-4100d — 2 of 3 edges lost)
- **First seen:** 2026-09-21 · **Last seen:** 2026-09-21
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py` — the `depends_on` derivation
  from `expects_from`
- **Distinct from KI-ACD-021**, which covers edges pointing at an AC's own *parent*. One
  of the two cases below is a parent edge and is explained by that entry; the other is a
  *sibling* edge and is not. The discriminator below explains both.

## Symptom

`depends_on` on a generated ticket is derived from the AC's `expects_from`, but only
sometimes. Observed across four records generated in one pass, from the same tree, with
the same field shapes:

| AC | `delivers_to` | `expects_from` | ticket `depends_on` |
|---|---|---|---|
| `BO-4100d-1` | populated | — | `[]` — correct, nothing to resolve |
| `BO-4100d-2` | **null** | `BO-4100d-1` | `[]` — **dropped** |
| `BO-4100d-3` | populated | `BO-4100d-1` | `[TICKET-…d-1.md]` — resolved |
| `BO-4100d-3-i` | **null** | `BO-4100d-3` | `[]` — **dropped** |

`d-2` and `d-3` declare `expects_from` against the *same* target (`BO-4100d-1`), in the
same shape, and were generated minutes apart into the same tickets root. One resolved and
one did not.

## The discriminator

The edge is honoured only when the *consuming* AC also has a non-null `delivers_to`. An AC
that consumes a contract but produces none — which is exactly what a terminal leaf looks
like — loses its incoming edge.

That is the worst possible population to lose: terminal leaves are the ends of every
contract chain, so the dependency information disappears precisely where ordering has no
other signal to fall back on.

This appears to be the same seam as KI-ACS-013 (`delivers_to` and `expects_from` are the
two ends of one edge keyed on different things, so the forward half is not traversable),
surfacing as a different consequence: there it is a traversal gap, here it silently
conditions the reverse edge on the forward one being present.

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
