---
title: "KI-ACS-20260907-0920 — Nothing compares an AC's fields against each other, so a record can carry two clauses that contradict — and in one case the contradicted clause predicted verbatim the defect that shipped"
description: "KI-ACS-20260907-0920 — Nothing compares an AC's fields against each other, so a record can carry two clauses that contradict — and in one case the contradicted clause predicted verbatim the defect that shipped"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260907-0920 — Nothing compares an AC's fields against each other, so a record can carry two clauses that contradict — and in one case the contradicted clause predicted verbatim the defect that shipped

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2 (both found 2026-09-07 while reading records for other reasons)
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `scripts/ac_store/validate_ac_schema.py` and the `AC store valid` required CI
  gate — both validate each field's *shape* against `config/ac_store_schema.json`; neither
  compares one field's *content* against another's. Also the PO/BA/IT-PO authoring gates,
  which approve a record without a self-consistency pass.

**The gap in one line.** Every check on an AC record is either per-field (is this a string,
is this enum member valid) or cross-record (does this parent's `covered_by` list its
children). **Nothing is cross-field within a single record** — not requirement-vs-requirement,
not requirement-vs-criteria, not `expects_from`-vs-`notes`. A record can therefore state a
thing and its negation, pass the required gate, and be approved.

Both instances below were found by a human reading the record. That is the only detector
there is.

**Instance 1 — `BP-1500d-3.yaml`, and this is the consequential one, because the losing
clause was right.**

Verified 2026-09-07 in a worktree at `origin/main` (`e2b1eb7ea`), quoted verbatim.

`expects_from: BP-1500d-1` (`:95`) states the consequence of building `-3` without `-1`:

> "…plus the ability to place that harness in a state where the record CAN be produced. The
> second half is what makes this AC's paired success run possible; **without it only the
> failure verdict is observable and the AC can be satisfied by a build that refuses every
> out-of-package target.**"

`notes` (`:238`), recording the IT-PO's ordering conclusion:

> "Neither edge went into depends_on, so no cycle exists between -1 and -3; **they can land
> in either order.**"

**Why the second is wrong and the first is right.** The "either order" reasoning is a
*cycle* argument — it establishes only that no dependency loop exists, which is true. It
then reports that result as an *ordering* verdict, which does not follow. Read the two
cases separately and the asymmetry is immediate: `-1`-first is fine, and that is the case
the note examined; `-3`-first leaves only the failure verdict observable, and that case was
never analysed. It is the broken one.

**This shipped.** `BP-1500d-3` was built before `-1`. The outcome is the one its own
`expects_from` names in advance — a build satisfying the AC by refusing every out-of-package
target. The record contained the warning, three clauses from the conclusion that overrode it,
for the entire time.

**Instance 2 — `ACS-1300a-1-i.yaml`, already repaired, recorded because the repair is the
evidence.** An earlier enrichment carried an `it_requirements` clause forbidding the trimming
of a trailing punctuation character alongside another requiring a trailing comma be
normalised away. Mutually exclusive; both approved.

It is **no longer live** — do not go looking for it in the file. It was corrected in place on
2026-09-01, and the correction is what documents it: `it_requirements[1]` (`:52`) now opens
*"CORRECTED 2026-09-01, AND THIS SUPERSEDES THE EARLIER 'MUST NOT TRIM A TRAILING PUNCTUATION
CHARACTER' REQUIREMENT, WHICH WAS WRONG AND CONTRADICTED ITS OWN NEIGHBOUR"*, and the
amendment note (`:140-144`) records the contradiction so it is *"not reintroduced"*.

That repair is a good outcome and it is also the finding. The record was approved carrying
the contradiction, no gate objected at any point, and it was fixed only because someone read
the two clauses side by side and noticed. Instance 1 is what the same absence costs when
nobody happens to read carefully enough in time.

**Why "an author should be more careful" is the wrong fix.** These clauses are far apart in a
long record — 143 lines apart in instance 1 — written at different times by different agents
(BA, then IT-PO amendment), and each is locally reasonable. The contradiction exists only in
the pair. That is precisely the shape a mechanical comparison is good at and a sequential
reader is bad at.

**Fix direction, cheapest first.**

1. **Make the ordering claim checkable, not prose.** An `expects_from` contract that says a
   dependency's absence weakens this AC's own verification *is* an ordering constraint. Either
   mirror it into `depends_on` or add a validator rule that refuses a `notes` ordering verdict
   contradicting a live `expects_from`. Note this is the same field pair as `KI-ACD-015`, from
   the other side: that entry is about `expects_from` being invisible to the **sequencer**;
   this one is about it being invisible to the **record's own reasoning**. A validator rule
   asserting `expects_from`/`depends_on` agreement — which `KI-ACD-015` already proposes as
   its fix — would catch instance 1 as a side effect. **Fixing that one rule closes both.**
2. **A cross-field review pass at approval.** An authoring gate that reads the record's
   clauses pairwise and asks only "can both of these be true at once". Cheap, catches
   instance 2's shape, and needs no schema change.

**A trap for whoever fixes this.** Do not model it as "reject contradictions". Instance 1's
two clauses are not formally contradictory — one is about cycles, one about ordering; they are
both true statements about different things. What was wrong was treating the cycle result as
answering the ordering question. A rule that only catches literal negation-pairs would have
caught instance 2 and missed instance 1, which is the expensive one.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a check whose scope excludes the
place the defect lives. Every field in both records passed every check that exists; the
defect was in the relationship between fields, which no check has ever looked at.

**Related.** `KI-ACD-015` (`expects_from` invisible to the build sequencer — same field pair,
and its proposed validator rule would close instance 1 here); `KI-ACS-013` (`delivers_to` and
`expects_from` keyed on different things, and *"nothing validates either"* — the structural
half of the same unvalidated-contract surface).

---
