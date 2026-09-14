---
title: "Oversized files must now get smaller when you add to them, not merely stop growing"
date: "2026-09-14"
time: "19:10"
type: manual
components:
  - commit_guardian
  - ac_store
summary: "The ratchet guarantees an over-long file cannot get bigger, which freezes the backlog at 212 files and 62,524 excess lines forever. A new criterion requires that adding to such a file leaves it smaller than you found it — by twice what you added, capped at the size standard, and free when you add nothing."
description: "New L1 GE-127f with three L2s and one L3; specification only, no code. The rule is a single end-state comparison: a change to an already-oversized file must leave it at or below max(limit, previous_length - added). That carries the 2x effect on large files, caps the demand at the size standard for files near the line, keeps zero-addition changes free, and self-terminates when a file reaches the limit. Chosen as a new sibling rather than an amendment to GE-127b, because GE-127b's value is that compliance costs nothing and folding a price into it makes that false. Two of the four requirements behind it are not mechanically enforceable at a commit gate, and the records say so rather than faking them. GE-127f-3 is deliberately left unenriched pending INF-800f."
commits:
  - 8b0822430
breaking: false
---

## Entry

### What was missing

`GE-127b` guarantees an over-long file cannot get **bigger**. Its own notes claim the
oversized population is "monotonically non-increasing" — and that is precisely what it
delivers. Nothing ever forces the decrease.

Measured today: **212 of 988 tracked Python files** are over 400 counted lines, carrying
**62,524 excess lines**. Left alone, that number is the same next year.

### The rule

> A change to an already-oversized file must leave it at or below
> **`max(limit, previous_length − added)`**.

One end-state comparison, not a removal quota, and it carries four properties at once:

| situation | outcome |
|---|---|
| 2,677-line file, add 50 | target 2,627 — net −50, the 2× effect |
| 410-line file, add 50 | target **400** — sixty lines leave, not a hundred |
| add nothing | target = previous — free |
| file reaches the limit | leaves the regime; the ordinary threshold governs |

The cap matters as much as the multiplier: nobody refactors 200 lines when 20 would bring
the file under.

It is calibrated against the real distribution rather than a round number. Bands run
78 / 77 / 29 / 19 / 9 across 400–500 / 500–700 / 700–1000 / 1000–1500 / 1500+, median
551 — so 73% of the backlog sits within ~300 lines of compliance, and 2× clears most of it
in one or two growth-shaped changes where 1.2× would take ten and in practice never
happen. The nine files above 1,500 will not be fixed incidentally at any multiplier.

### Why a new criterion rather than a stronger ratchet

`GE-127b`'s entire value proposition is that compliance costs the author **nothing** —
that is what let the size standard switch on across 212 files without stopping work, and
its notes call the allow-arm *"not a concession; it is the mechanism."* Folding a price
into the record whose tagline is "free" makes that tagline false, and hands an implementer
a pair it can satisfy by building whichever half is cheaper.

`GE-127b` is also delivered and green. The narrowing is recorded against it properly —
`amended_by` plus a forward link, `criteria` untouched — rather than by reopening finished
work.

### Two requirements that a commit gate cannot enforce, stated plainly

A commit is one diff under one identity. **Nothing at commit time distinguishes "the coder
removed 100 lines" from "the specialist removed 100 lines."** And moving *new* code out of
an oversized file — which is desirable — looks identical in a diff to moving *existing*
code out to satisfy a quota, which is the failure.

Both are real guarantees, but they live in workflow sequencing, not in a gate. The records
say so and express the seam as a contract on build-orchestration, with an explicit
prohibition on specifying dispatch mechanics inside the hook.

`GE-127f-3`, which carries that half, is **deliberately left unenriched**: it is blocked on
`INF-800f`, and writing a machine-checked spec against a dispatch contract that does not
exist yet is the mistake this store already made once with `BP-100k-4`'s declared-but-never
-created config keys.

### Three exposures named rather than quietly inherited

**`count_content_lines` strips triple-quoted regions and block comments only** — not `#`
comments, not blank lines. Probe: three `#` lines count as 3, four blanks count as 4. So
deleting whitespace remains a valid way to satisfy a removal demand, and the incentive
scales with the multiplier. Closing it means reclassifying what counts, which is
`GE-127d`'s call — so it is routed there, with no second counting rule written into the
comparison, and a fixture constraint that every passing arm must reach its end state by
whole definitions leaving the file.

**A change adding only docstrings is free, and can be arbitrarily large** — because
additions must be counted in the file's own unit or there would be two counting rules.
Recorded as a known accepted consequence, with the relevant arm required to use a
deliberately large fixture so a future reader meets a documented decision rather than a
surprise.

**A delivered test is narrowed on purpose.** `GE-127b-1`'s boundary descriptor asserts a
same-length change commits; under `GE-127f` that holds only for zero-addition changes. It
is neither deleted nor weakened — its fixture is pinned, and a seam descriptor builds both
fixtures in one test so the narrowing is observed rather than discovered as a mystery red.

### Verification

`OK: all 4036 AC YAML files are valid.` `package_surface: false` on all three enriched
records, measured against `WATCHED_REGISTRIES`. `declares_side_effect: false` on all three
— not judged but computed, by running `derive_declares_side_effect` directly, since
`validate_ac_schema.py` does not run that derivation and a clean standalone validation is
no evidence on that field.
