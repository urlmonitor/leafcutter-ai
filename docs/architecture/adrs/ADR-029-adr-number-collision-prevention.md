---
title: "ADR-029: ADR Number Collision Prevention — Pre-Commit Guard Over the Integer Sequence"
description: "Decision to keep the flat integer ADR sequence and defend it with a pre-commit collision guard plus a repository-wide citation audit, rather than renumbering the corpus or introducing a reservation file. Amended 2026-08-18 to narrow the fail-open rule to the guard's own internal defects, so a guard that could not read the sequence no longer exits 0."
type: "adr"
status: "active"
created: "2026-08-13"
last_updated: "2026-08-18"
deciders:
  - BrainCandy
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/conventions/adr-numbering.md
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3.yaml
  - docs/acceptance-criteria/guardrail-engine/GE-122-numbers-mean-one-thing/GE-122d-3-i.yaml
related_code:
  - templates/scripts/commit_guardian/check_adr_collision.py
  - scripts/adr_refs.py
  - templates/agents/adr-author.md
---

# ADR-029: ADR Number Collision Prevention — Pre-Commit Guard Over the Integer Sequence

## Status

| Field | Value |
|---|---|
| Status | Accepted, amended |
| Date | 2026-08-13 |
| Amended | 2026-08-18 — Amendment 1 (fail-open narrowed; wiring claim corrected). See [Amendment 1](#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects). |
| Deciders | BrainCandy |
| Author | Retroactive record for `check_adr_collision.py`, written during the 2026-08-13 numbering repair |
| Context ADRs | ADR-001 (self-hosting boundary) |

> **Read the Decision section together with [Amendment 1](#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects).** The
> unqualified fail-open rule below has been narrowed, and the Context section's claim
> that the guard is wired into `.pre-commit-config.yaml` is false. Both are corrected
> in place and explained at the end of this record.

## Context

`adr-author` picks the next ADR number by scanning `docs/architecture/adrs/ADR-*.md`
for the highest existing integer and incrementing. That is correct for serial work and
racy under concurrent worktrees: each branch's scan sees only what is committed on
`origin/main`, so two branches can independently claim the same number. Because the
filenames differ, git reports no conflict — the collision surfaces post-merge as a
logical ambiguity, and a bare `ADR-NNN` citation stops resolving to a single decision.

`check_adr_collision.py` was written to close this gap and has been shipped since the
package's early history. **Its own decision record was never written in this repository**
— the hook, `templates/agents/adr-author.md`,
and `docs/conventions/adr-numbering.md` all cite "ADR-029" as the record, and until now
that number owned no file. This ADR is that missing record, written retroactively at
the number the existing citations already use.

Two things forced the issue on 2026-08-13. First, the guard is only a *forward* defence:
it stops new collisions but is blind to ones already merged. An audit found four
duplicated integers (`004`×2, `007`×3, `017`×3, `025`×2 — ten files on four numbers) and
382 bare citations that no longer resolved to one decision. Second, the guard had no
authority to point at, so its policy was undocumented and unreviewable.

> **Correction, 2026-08-18.** The sentence above originally read "has been shipped **and
> wired into `.pre-commit-config.yaml`** since the package's early history". That was
> false when written and is false now: `check_adr_collision.py` appears in none of the 49
> hook entries in `templates/scripts/commit_guardian/commit_guardian.json`, from which
> `.pre-commit-config.yaml` is generated, and therefore in none of the generated config.
> The guard is deployed but has never run. This is not a footnote — everything the
> Decision section below says about a forward defence describes a hook nobody invokes, so
> the collisions this record was written to prevent have been unguarded throughout. See
> [Amendment 1](#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects).

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

The guard is **fail-open for its own defects, and fail-closed when it could not read the
sequence.** *(Amended 2026-08-18. This paragraph originally read: "The guard is
**fail-open**: any unexpected error (git unavailable, directory absent, network failure)
warns on stderr and exits 0. It must never become a deployment blocker on a fresh machine
or in CI." That unqualified rule is withdrawn — see
[Amendment 1](#amendment-1--2026-08-18--fail-open-is-narrowed-to-the-guards-own-defects)
for why.)*

The boundary is drawn on **whether the guard managed to read the whole sequence**, not on
which exception it caught:

- **It read every number, then something in its own reporting code failed** → warn on
  stderr, exit 0. The sequence *was* inspected; a bug on the way to saying so must not
  hold an unrelated commit hostage.
- **It could not read some or all of the sequence** — git unavailable, the ADR directory
  absent, the remote-branch scan failing — → say so, name what it could not read, report
  how many numbers it *did* read, and **do not exit 0**. Nothing was established, so
  reporting success would certify an unexamined sequence.

Deciding this on exception class instead of read completion is the implementation to
reject at review: it passes every test written today and silently inverts the boundary
the first time an unfamiliar exception crosses it.

The guard still cannot see branches that exist only on another developer's machine, so it
remains best-effort against *unpushed* work. That limit is a property of what it can
observe, and is unaffected by this amendment — an unpushed branch is not a read failure,
because there is nothing there for the guard to fail to read.

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
- A defect in the guard's own reporting still passes rather than blocking — deliberately,
  so that a bug in the guard cannot stop every commit in the repository. *(Amended
  2026-08-18. Originally: "Fail-open means a broken guard passes silently rather than
  blocking." It no longer passes **silently**, and it no longer passes at all when the
  failure was an inability to read the sequence.)*
- Fail-closed on a read failure means a genuinely broken environment — no git, no ADR
  directory — now blocks the commit. That is the intended cost, and it is the reason the
  boundary above has to be precise: too broad, and a fresh checkout cannot commit.
- `adr_refs.py` must be run deliberately; it is not yet a required CI gate.

### Neutral

- The sequence stays flat, so ADR numbers carry no semantic structure beyond order.

## Alternatives Summary

| Option | Verdict | Reason |
|---|---|---|
| A — Reservation file | Rejected | Recreates the conflict at a new layer |
| B — Prefixed numbering | Rejected | Corpus-wide rename; breaks every citation |
| C — Pre-commit guard + audit | **Chosen** | No migration, no renaming, covers both directions |

## Amendment 1 — 2026-08-18 — Fail-open is narrowed to the guard's own defects

| Field | Value |
|---|---|
| Amends | The Decision section's forward-guard paragraph, and one factual claim in Context |
| Status | Accepted |
| Deciders | BrainCandy |
| Driven by | `GE-122d-3`, `GE-122d-3-i` (goal `GE-122`, "numbers mean one thing") |
| Supersedes this ADR? | No. Options A/B remain rejected; the flat sequence and the guard-plus-audit structure are unchanged. |

### Why this had to change

`GE-122d-3` requires that a uniqueness pass which could not see the whole collection must
not report success — it names the artifact it could not read, states that uniqueness was
not established, reports how many artifacts it *did* read, and blocks at commit time.
`GE-122a-1` requires that pass to cover the decision-number namespace by adopting
`check_adr_collision.py` rather than writing a second guard beside it.

Those two requirements met this record's original wording head-on. "Any unexpected error
… warns on stderr and exits 0" is broad enough to cover exactly the case `GE-122d-3` says
must block. Shipping the AC without touching this ADR would have left accepted code
contradicting an accepted decision, with no note anywhere saying which one a reader should
believe — which is the same class of defect as the numbering drift the goal exists to fix,
one layer up. The IT PO flagged the conflict at enrichment time and required the amendment
to land *with* the behaviour change rather than after it. This amendment is that half; the
guard is not built yet.

### What the original rule got right, and where it overreached

The instinct behind fail-open is sound and is preserved: a bug in a guard must not stop
every commit in the repository, because a guard that blocks work indiscriminately gets
deleted, and a deleted guard protects nothing. The overreach was in the *reason given* for
exiting 0. "An unexpected error occurred" bundles two situations that deserve opposite
answers:

|  | Did it inspect the sequence? | Disposition |
|---|---|---|
| Bug in the guard's reporting, after the read | Yes | Announce, exit 0 |
| Cannot read the sequence at all | No | Announce, do not exit 0 |

The first has established that the sequence is clean and then tripped on the way to the
podium. The second has established nothing. Reporting success in the second case is the
claim "I could not check, therefore it is fine" — and that is worse in a whole-collection
check than in a per-file one, because a per-file check that cannot read its single input is
visibly broken, while a pass that reads 2,974 of 2,975 records looks exactly like one that
worked.

### The rule for implementers

Derive the disposition from the **per-namespace read counts**, which the pass tracks during
the walk. Do not derive it from the exception class, and do not wrap the entry point in one
blanket `try/except` — a blanket handler makes every failure look like an internal defect
and lets the unreadable-collection case through, which is precisely the inversion this
amendment exists to prevent. The proceed path keeps the component's established fail-open
tail shape (`check_ac_governance.py` is the reference): specific exception type, deliberate
`noqa: BLE001`, stderr-prefixed announcement, clean stdout.

### The unregistered-hook finding

While resolving this conflict we established that `check_adr_collision.py` is registered in
none of the 49 hook entries in `commit_guardian.json`, and so appears in no generated
`.pre-commit-config.yaml`. The Context section's claim to the contrary is corrected above.

This changes what this amendment *is*. Narrowing a fail-open rule on a hook that never runs
is not a behaviour change — it is a specification for a guard whose forward half has never
executed. Registration is therefore part of the work `GE-122` covers, not a separate
tidy-up, and `GE-122e-3` asserts it directly: an `"enabled": false` entry in
`hooks_manifest.hooks` (or, as here, no entry at all) removes a hook from the generated
config at build time and leaves no trace in the file a reader would inspect. Nobody has to
write an allowlist to switch a gate off.

Until that lands, the four duplicated decision numbers found on 2026-08-13 should be read
as what an unguarded sequence produces, not as history the guard has since prevented.

## References

- [Convention: ADR Numbering and Collision Prevention](../../conventions/adr-numbering.md)
- [`check_adr_collision.py`](../../../templates/scripts/commit_guardian/check_adr_collision.py) — the forward guard
- [`adr_refs.py`](../../../scripts/adr_refs.py) — the retrospective audit and repair tool
- [ADR-001 — Self-Hosting Boundary](ADR-001-self-hosting-boundary.md)
