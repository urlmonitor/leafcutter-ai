---
title: "ADR-029: ADR Number Collision Prevention — Pre-Commit Guard Over the Integer Sequence"
description: "Decision to keep the flat integer ADR sequence and defend it with a pre-commit collision guard plus a repository-wide citation audit, rather than renumbering the corpus or introducing a reservation file."
type: "adr"
status: "active"
created: "2026-08-13"
last_updated: "2026-08-13"
deciders:
  - BrainCandy
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/conventions/adr-numbering.md
  - docs/how-to/documentation/write-adr.md
related_code:
  - templates/scripts/commit_guardian/check_adr_collision.py
  - scripts/adr_refs.py
  - templates/agents/adr-author.md
---

# ADR-029: ADR Number Collision Prevention — Pre-Commit Guard Over the Integer Sequence

## Status

| Field | Value |
|---|---|
| Status | Accepted |
| Date | 2026-08-13 |
| Deciders | BrainCandy |
| Author | Retroactive record for `check_adr_collision.py`, written during the 2026-08-13 numbering repair |
| Context ADRs | ADR-001 (self-hosting boundary) |

## Context

`adr-author` picks the next ADR number by scanning `docs/architecture/adrs/ADR-*.md`
for the highest existing integer and incrementing. That is correct for serial work and
racy under concurrent worktrees: each branch's scan sees only what is committed on
`origin/main`, so two branches can independently claim the same number. Because the
filenames differ, git reports no conflict — the collision surfaces post-merge as a
logical ambiguity, and a bare `ADR-NNN` citation stops resolving to a single decision.

`check_adr_collision.py` was written to close this gap and has been shipped and wired
into `.pre-commit-config.yaml` since the package's early history. **Its own decision
record was never written in this repository** — the hook, `templates/agents/adr-author.md`,
and `docs/conventions/adr-numbering.md` all cite "ADR-029" as the record, and until now
that number owned no file. This ADR is that missing record, written retroactively at
the number the existing citations already use.

Two things forced the issue on 2026-08-13. First, the guard is only a *forward* defence:
it stops new collisions but is blind to ones already merged. An audit found four
duplicated integers (`004`×2, `007`×3, `017`×3, `025`×2 — ten files on four numbers) and
382 bare citations that no longer resolved to one decision. Second, the guard had no
authority to point at, so its policy was undocumented and unreviewable.

## Options Considered

### Option A — Branch-local reservation file

A `.reserved` file listing claimed numbers. Rejected: the file becomes a coordination
surface that itself conflicts when two branches both edit it, reproducing the problem
one layer up.

### Option B — Date- or branch-prefixed numbering

Replace the integer with something globally unique. Rejected: it requires renaming the
whole corpus, invalidates every existing citation, and discards the chronological
ordering that makes the sequence readable at a glance.

### Option C — Pre-commit collision guard over the existing sequence (chosen)

Keep the flat integer sequence and defend it at commit time.

## Decision

**Keep the flat, chronologically meaningful integer sequence. Defend it with two
mechanisms, one forward and one retrospective.**

### Forward: `check_adr_collision.py` (pre-commit)

Fires on staged files matching `^docs/architecture/adrs/ADR-.*\.md$`. It scans
`origin/main` for committed integers and remote branches for in-flight ones, compares
the staged number against both, and exits non-zero with the next free number when they
collide.

The guard is **fail-open**: any unexpected error (git unavailable, directory absent,
network failure) warns on stderr and exits 0. It must never become a deployment blocker
on a fresh machine or in CI. It also cannot see branches that exist only on another
developer's machine, so it is best-effort, not a guarantee.

### Retrospective: `scripts/adr_refs.py` (audit)

A pre-commit guard cannot see collisions that are already merged, and it says nothing
about whether citations still resolve. `adr_refs.py` walks the repository and reports
duplicated numbers, sequence gaps, citations to numbers that own no file, and citations
naming a slug that owns no file. It also regenerates the ADR index, so the index cannot
drift from the corpus.

### A number is free only when nothing cites it

The repair surfaced a rule the guard alone does not encode: a number with no file is not
necessarily available. Reusing a number that existing text still cites converts a
*dangling* reference into a confidently *wrong* one, which is worse. Treat a number as
free only when it has neither a file nor a citation — the "Unclaimed numbers" line of
`adr_refs.py` is the authoritative list.

## Consequences

### Positive

- Migration cost is zero; no existing citation is invalidated.
- Collisions are caught at the cheapest possible point, with the fix printed.
- The retrospective audit catches what the commit-time guard structurally cannot.
- The index is generated, so it cannot silently go stale.

### Negative

- The guard is best-effort: unpushed local branches remain invisible.
- Fail-open means a broken guard passes silently rather than blocking.
- `adr_refs.py` must be run deliberately; it is not yet a required CI gate.

### Neutral

- The sequence stays flat, so ADR numbers carry no semantic structure beyond order.

## Alternatives Summary

| Option | Verdict | Reason |
|---|---|---|
| A — Reservation file | Rejected | Recreates the conflict at a new layer |
| B — Prefixed numbering | Rejected | Corpus-wide rename; breaks every citation |
| C — Pre-commit guard + audit | **Chosen** | No migration, no renaming, covers both directions |

## References

- [Convention: ADR Numbering and Collision Prevention](../../conventions/adr-numbering.md)
- [`check_adr_collision.py`](../../../templates/scripts/commit_guardian/check_adr_collision.py) — the forward guard
- [`adr_refs.py`](../../../scripts/adr_refs.py) — the retrospective audit and repair tool
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md)
