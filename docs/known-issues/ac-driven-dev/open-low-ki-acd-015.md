---
title: "KI-ACD-015 — Epic ordering reads `depends_on` only, so `expects_from` contract edges are invisible to the build sequencer"
description: "KI-ACD-015 — Epic ordering reads `depends_on` only, so `expects_from` contract edges are invisible to the build sequencer"
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

# KI-ACD-015 — Epic ordering reads `depends_on` only, so `expects_from` contract edges are invisible to the build sequencer

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/goal_to_epic.py` (`_build_depends_on_index`,
  `_translate_ticket_depends_on`) — zero occurrences of `expects_from` in the file

**Symptom.** `goal_to_epic.py` builds its topological order purely from `depends_on`. The
AC schema also carries `expects_from: {ac_id, contract}`, which states that an AC consumes
a named contract from another AC — a build-order fact by any reading. The generator never
looks at it.

In the GE-120 tree three records declared a contract edge that existed **only** in
`expects_from`:

```text
GE-120b-1     expects_from GE-120c-1    depends_on: [GE-120b, ACS-1200a]
GE-120b-4     expects_from GE-120c-1    depends_on: [GE-120b, GE-120b-2]
GE-120b-1-i   expects_from GE-120a-2    depends_on: [GE-120b-1]
```

`GE-120c-1` is the out-of-process harness that `b-1` and `b-4` are *verified through*.
Without the edge the sequencer is free to schedule both before the harness exists. The
edges were added to `depends_on` by hand before generating, and the resulting order put
`c-1` at position 12 ahead of `b-1` (13) and `b-4` (15) — so the mechanism works, it is
simply fed from one field when the store records the dependency in two.

**The open question is which field is authoritative,** and the answer is not obvious.
`expects_from` may be intended purely as contract documentation with `depends_on` as the
scheduling field. If so the defect is in the ACs (an IT-PO that writes `expects_from`
should mirror it into `depends_on`) and the fix is a validator rule, not a generator
change. If instead `expects_from` is meant to be load-bearing, the generator must read it.
Deciding this is a prerequisite to fixing it — implementing either half without the
decision produces two sources of truth for build order.

**Detection cost today.** Nothing surfaces the discrepancy. It was found by diffing
`expects_from.ac_id` against `depends_on` across the tree by hand. Whichever direction is
chosen, a store rule should assert the invariant.

---
