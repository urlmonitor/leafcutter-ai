---
title: "KI-ACD-023 — The generated `files_touched` surface admits bare directories and incidental prose while excluding the deliverable the record creates"
description: "KI-ACD-023 — The generated `files_touched` surface admits bare directories and incidental prose while excluding the deliverable the record creates"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-023 — The generated `files_touched` surface admits bare directories and incidental prose while excluding the deliverable the record creates

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2 (five records in one epic; then 10 of 27 in a second)
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-31
- **Where:** `scripts/ac_store/generate_ticket_from_ac.py::_build_files_touched` — the
  prose-token extractor and its on-disk existence gate
- **This is the entry that stopped a live drive.** See the 2026-08-31 recurrence at the end.

**Symptom.** `files_touched` on a generated ticket is not a reliable statement of the record's
edit surface. Three failure directions, all observed in `EPIC-StartingNewWorkTheProperWayAlways`
(#596) and repaired by hand in #604:

| Direction | Observed |
|---|---|
| Empty when it should not be | 4 of 25 tickets — `ACD-2100d-1`, `-d-2`, `-d-2-i`, `-d-3` |
| Populated but wrong | `ACD-2100d-4` — three incidental prose mentions, **omitting the one document the record creates** |
| Too wide | ticket 24 (`ACD-2100e-1`) carries the bare directory `docs/architecture` |

**Cause.** The surface is the union of two derivations, and both leak:

1. **Path tokens in `it_requirements` prose that exist on disk.** Any slash-bearing token an
   author writes descriptively enters the surface, including bare directory names. Conversely
   the existence gate drops any path that does not exist *yet* — which is precisely the shape
   of a deliverable the record is written to create.
2. **`doc_links` whose `relationship` is one of `constrains` / `creates` / `implements` /
   `modifies` / `specifies`.** A record whose links are all `describes` contributes nothing.
   The whole `ACD-2100d` family carried only `describes` links and named no paths in prose, so
   every list came out empty.

**Why this is high.** `files_touched` drives the surface `change-scope-reviewer` and the AC
fulfillment gate reason about. The failure is not that the field is untidy — it is that each
direction defeats the gate differently, and the middle one is the worst:

- **Empty** is visibly unusable, but it fails *open*: a reviewer with nothing to compare
  against sees every diff as in-scope, and a ticket that changed nothing looks equally fine.
- **Populated-but-wrong is worse than empty**, because it does not look broken.
  `ACD-2100d-4`'s list looked like a considered answer while consisting entirely of incidental
  mentions and omitting its actual deliverable — so the real work would have read as
  *out of scope* to a reviewer, which is the inverse of what the field is for.
- **A bare directory** silently widens the surface to everything beneath it.

This repo has a recorded history of wrong `files_touched` producing phantom-done
(`EPIC-PhantomDoneFilesTouched`, and the CLAUDE.md rule that came out of it). The defect is in
the generator, so it applies to **every** ticket the AC-first path produces — which is the
mandated path for all new work under ADR-012.

**Also a trap for authors, not just a generator bug.** Because prose tokens are extracted, an
`it_requirement` that mentions a real path descriptively silently changes the ticket's scope
gate. There is no way for an author to refer to a file without listing it, and nothing warns
them. Any fix should give authors an explicit way to say "this path is context, not surface".

**Fix direction.** Stop deriving the surface from prose. Take `files_touched` from `doc_links`
alone, where the relationship vocabulary already distinguishes edit surfaces from references,
and give not-yet-existing deliverables a first-class representation instead of dropping them
at an existence gate — the `creates` relationship already exists for this and is the one thing
that currently survives. Reject bare directories, or expand them explicitly. Until then, the
manual workaround is the one applied in #604: mark the created deliverable's link `creates`,
and check every generated `files_touched` against the criteria before driving the ticket.

**Related.** `KI-ACD-014` (absolute `implemented_by` paths from the same generator),
`KI-ACD-016`, `KI-ACD-018` (the other three generator-output defects from the same family).
`ACD-2100d-1` … `-d-4` carry the repaired lists and dated `IT PO ENRICHMENT` notes recording
the per-path reasoning.

**2026-08-31 — second occurrence, larger, and it aborted a running build.**

`/build-feature` was launched over `EPIC-SuppressionNarrowsNeverDisables` (27 tickets) and
**stopped mid-drive** on this defect, after the planner and ~21 phase agents had started but
before any coder phase ran. **10 of 27 tickets** had an unusable surface — all three directions
this entry already names, at four times the scale:

| Direction | Count | Tickets |
|---|---|---|
| Empty | 4 | `GE-123c-3`, `GE-123d-2`, `GE-123d-4`, `GE-123d-5` |
| Populated but wrong | 2 | `GE-123d-3`, `GE-123d-4-i` |
| Bare directories only | 3 | `GE-123a-1-i`, `GE-123a-2`, `GE-123a-3` |
| Bare directories mixed with real files | 1 | `GE-123a-1` |

The three directory-only tickets each carry exactly
`['docs/acceptance-criteria', 'docs/retrospectives', 'templates/skills']` — three bare
directories and not one file. A coder handed that has no edit surface at all, and a scope
reviewer handed it will accept any change under three top-level trees.

**The populated-but-wrong pair is the reason the drive was stopped rather than paused.** Both
`GE-123d-3` and `GE-123d-4-i` came out as exactly `['docs/known-issues/commit-guardian.md']`
— *this file*. `GE-123d-3` is about the secrets scanner announcing a withheld finding; its
`doc_links` are three entries, **all `relationship: related`**, of which this register is the
last. With no `creates`/`modifies` link to draw on, the derivation reached past the
relationship vocabulary and took a pure context reference as the edit surface. Two coder agents
were minutes away from being pointed at the known-issues register as the file to modify, on
tickets about scanner behaviour — and the register had been extended with four new entries
that same hour.

That is this entry's "populated-but-wrong is worse than empty" case, realised: neither ticket
looks broken, both name a real file that really exists, and the wrongness is only visible if
you know what the AC is about.

**What this adds to the fix direction.** The existing prescription — take the surface from
`doc_links` alone — is necessary but **not sufficient**, and this run shows why: a record whose
links are *all* `related` must yield an **empty** surface and say so, never a context document.
Restricting to `creates`/`modifies`/`implements`/`specifies`/`constrains` does that, provided
the fallback is refusal rather than "use whatever links exist". Pair it with a generator-side
refusal to emit a ticket with an empty surface, so the gap surfaces at generation time instead
of at drive time.

**Detection before driving, which is now the operative advice.** Do not drive a generated epic
without auditing the surfaces first:

```
grep -A6 '^files_touched:' tickets/00_inbox/epics/<EPIC>/*.md
```

Look for three things: an empty list, an entry with no file extension, and any path whose
relationship to the ticket's own title you cannot state in a sentence.

**Pattern:** a derived field whose derivation is invisible to its author, failing in three
directions at once — and whose most damaging failure is the one that looks correct.

---
