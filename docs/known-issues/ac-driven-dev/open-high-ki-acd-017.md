---
title: "KI-ACD-017 — Epic generation re-scans the whole AC store per ticket, so its cost is tickets × store size and the store only grows"
description: "KI-ACD-017 — Epic generation re-scans the whole AC store per ticket, so its cost is tickets × store size and the store only grows"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-12'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-017 — Epic generation re-scans the whole AC store per ticket, so its cost is tickets × store size and the store only grows

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-10-12
- **Where:** `scripts/goal_to_epic.py` → per-ticket `generate_ticket_from_ac.py`, plus
  `_translate_ticket_depends_on` and the Master_Plan dependency map

**Symptom.** `goal_to_epic.py --ac GE-120` took **~30 minutes of wall clock at 30-55% CPU**
to produce 37 tickets — roughly 50 seconds per ticket, against a `--dry-run` that resolves
the same 37-leaf set in about a second. Time is spent re-loading and re-walking the AC
store (3,000+ records) once per ticket, then again during dependency translation and
Master_Plan assembly.

**Second occurrence, 2026-08-26 — and it is why this was re-rated from low to high.**
`goal_to_epic.py --ac ACD-2100` generated **25** tickets and was still running at **~40
minutes**. Set against the first run, the direction is the wrong one:

| Run | Tickets | Wall clock | Per ticket | Store size |
|---|---|---|---|---|
| `--ac GE-120`, 2026-08-25 | 37 | ~30 min | ~49 s | ~3,000 records |
| `--ac ACD-2100`, 2026-08-26 | 25 | ~40 min (unfinished) | ~96 s | 3,546 records |

**Fewer tickets, more time, one day apart.** Roughly twice the per-ticket cost for a
smaller epic. The store grew ~18% between the two runs, which does not by itself account
for a 2× move — the exact constant is not established here and the entry does not claim
one — but the shape is not in doubt: the work is `tickets × store size`, and one of those
factors is monotonically increasing. 25 tickets against 3,546 records is on the order of
**89,000 YAML parses of the same files**.

**Why this is high and not merely slow.** Severity here is not about the wait.

- **It gets worse on its own.** Every AC anyone authors makes every future epic
  generation slower, forever. No one changes the generator and no one notices the
  regression, because the code is unchanged and only the input grew. A defect that
  degrades without anyone touching it, on a store this project exists to grow, does not
  belong in the same band as a cosmetic annoyance.
- **It taxes the path the project wants people to take.** `/build-ac` is the mandated
  route for new work (ADR-012, CLAUDE.md). Making the sanctioned entry point the slowest
  one pushes people toward hand-written tickets, which is the exact behaviour the AC-first
  rule exists to prevent.
- **The fix is not proportionate to the cost.** One scan held in memory would serve all
  tickets — 3,546 parses instead of 89,000. The shared store index with an mtime cache
  that the commit-guardian AC hooks already use exists for precisely this; the generator
  simply does not use it. This is a low-effort fix carrying an unbounded, compounding cost,
  which is the combination that argues for raising the number rather than lowering it.

**The silence compounds it, and that part is unchanged.** The run produces no incremental
output — `tail` buffers everything to the end — so for the whole run there is no way to
distinguish progress from a hang. During the first run the loose tickets sat in
`tickets/00_inbox/` for ~20 minutes before being moved into the epic folder, and that
intermediate state was misread as a duplicate-ticket defect. A long silent run invites
wrong conclusions about its own correctness, and invites a user to kill it partway, which
would leave exactly the half-assembled state that was feared. The longer the run gets, the
more likely that kill becomes.

**Fix direction.** Load the store once and pass it down rather than re-reading per ticket,
reusing the existing shared store index rather than adding a third reader of the same data.
Emit a per-ticket progress line so the run is legible while it is happening. A regression
test should assert the store is read a bounded number of times independent of ticket count
— asserting a wall-clock budget would encode today's store size and rot immediately.

**Third occurrence, 2026-10-12: `--ids`, 48 tickets, over ten minutes.** Scaffolding
`EPIC-RightJobRightAgent` (48 ids, store at 5,022 YAML files) took more than ten minutes. That
figure was reported by the session and not timed precisely. It works out to over 12 s per ticket.
The shape is unchanged, and two per-ticket whole-store passes were verified in code on origin/main
`a104d934`:

- **One generator subprocess per ticket.** `epic_tickets.generate_tickets_for_leaves`
  (`:212-216`) calls `_call_generate_ticket_from_ac` (`:118-180`). Each call starts a fresh
  interpreter, which finds its AC by walking the whole store (`_gtfa_store._find_ac_by_id`,
  `rglob` at `:79`).
- **One in-process whole-store walk and parse per ticket in the repoint pass.** After assembly,
  `epic_phases._apply_epic_backrefs` (`:198-202`) calls
  `epic_assembly._replace_implemented_by_entry` (`rglob` at `:321`) once per ticket. That is
  about 48 × 5,000 YAML parses to rewrite 48 lines. On Windows the pass also rewrites nothing
  (`KI-BO-014`, Occurrence 2).

The run prints nothing per ticket. Subprocess output is captured, and only the `Written:` line is
read, so this entry's silence point also holds for `--ids`. What the run did print part-way
through was a reader-thread traceback; see
`KI-ACD-20261012-epic-generator-child-output-decoded-with-the-wrong-codec`.

---
