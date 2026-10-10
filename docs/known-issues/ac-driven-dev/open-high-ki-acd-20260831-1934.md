---
title: "KI-ACD-20260831-1934 — A ticket's `depends_on` models lifecycle status where the real requirement is an artifact, and on an L2 with a Roman child that closes a cycle no run can exit"
description: "KI-ACD-20260831-1934 — A ticket's `depends_on` models lifecycle status where the real requirement is an artifact, and on an L2 with a Roman child that closes a cycle no run can exit"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-09'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20260927-goal-to-epic-scaffold-fails-frontmatter-check.md
---

# KI-ACD-20260831-1934 — A ticket's `depends_on` models lifecycle status where the real requirement is an artifact, and on an L2 with a Roman child that closes a cycle no run can exit

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC
- **Occurrences:** 2 epics. ACD-2100d-2 / ACD-2100d-2-i, blocking two drives (2026-08-31).
  EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, in two shapes (2026-09-28 and 2026-09-30); see
  "Observed again" below.
- **First seen:** 2026-08-31 · **Last seen:** 2026-09-30
- **Where:** ticket `depends_on` as consumed by the epic planner and
  `ticket_prioritizer` ("Done tickets satisfy depends_on for other tickets"), interacting
  with `check-ticket-ac-status-parity` and the parent/child composite rule

**Symptom.** A four-step cycle with no exit:

```
21 depends_on 20                       21 cannot start until 20 is done
ticket 20 done   requires ACD-2100d-2 done      (check-ticket-ac-status-parity)
ACD-2100d-2 done requires ACD-2100d-2-i done    (parent/child composite rule)
ACD-2100d-2-i is delivered by ticket 21         20 cannot finish until 21 does
```

Each link is individually correct and defensible. Together they are unsatisfiable.

**Cause.** `depends_on` expresses ordering as *ticket lifecycle status*, but what
`ACD-2100d-2-i` actually needs from `ACD-2100d-2` is its **code** — the installer-derived
mapping and per-file divergence determination, which `ACD-2100d-2`'s own contract describes
as "consumed as a callable determination". That artifact was committed and on the branch
while the dependency still read as unmet, because the dependency was pointing at a status
field rather than at the thing it needs.

**Why this shape recurs.** It needs an L2 whose Roman-suffixed constraint child is built by a
ticket that depends on the L2's own ticket. That is not exotic — it is the default shape the
generator produces for any `X` / `X-i` pair, and CLAUDE.md already records that L2-done-with-
Roman-child-todo is the dominant falsely-done composite (13 of 20 in the last store sweep).
Any such pair where the `-i` ticket declares `depends_on` on its parent's ticket will
deadlock the same way.

**The tempting wrong exit.** `check-ticket-ac-status-parity` reads only the named AC's *own*
`work_status`, and the parent/child check validates the staged set — so marking the parent
`done` and simply not staging the unchanged child passes every gate. That is the "hooks see
the index, so their silence is not a pass" gap, and using it manufactures exactly the
falsely-done composite the composite rule exists to prevent. It was rejected here for that
reason.

**Fix direction.** Distinguish an artifact dependency from a lifecycle dependency. A ticket
that needs another's *output* should express that as `expects_from` (which already exists and
already carries the contract text) and should not also carry a `depends_on` edge that gates on
status. Reserve `depends_on` for genuine ordering — cases where the earlier ticket's *record*
must be closed, not merely its code present.

**Workaround applied.** `ACD-2100d-2-i`'s `depends_on` was emptied by explicit decision, with
the reasoning recorded on the ticket. The ordering that genuinely matters — that this record
must not modify the files computing the determination — lives in the implementation notes,
not in `depends_on`, and is unaffected.

**Pattern:** an ordering constraint expressed against a proxy (status) for the thing it
actually requires (an artifact), so it stays unsatisfied after the requirement is met.

## Observed again, 2026-10-09

Filed after the BO-4300 drive (EPIC-EveryPieceOfSeparateWorkGetsItsWorkspace, branch
`epic/every-piece-of-separate-work-gets-its-workspace`). The cycle appeared twice, in two shapes.
The `/build-feature` planner still counts a dependency as met only when the ticket is recorded
complete or reads `status: done` (`templates/workflows-js/build-feature.js:3078` on `origin/main`
`c373b005e`).

**Shape 1: every child depends on its composite parent (2026-09-28).** The generated epic had one
ticket per leaf AC, and each child ticket depended on its parent's ticket. A parent can only be
`done` when its source AC is done (`check-ticket-ac-status-parity`), and a composite AC cannot be
done before its children (`check-done-proof`). So the epic deadlocked after ticket 01. Commit
`5395fad54` reversed the edges for the 17 parents ("parents close last"). The generator side is on
`KI-BO-20260927-goal-to-epic-scaffold-fails-frontmatter-check`.

**Shape 2: an AC needs a later ticket's code (2026-09-30).** Ticket 02's AC BO-4300f-4 has a
sub-test that needs BO-4300b-1, which ticket 04 builds. Ticket 02's code was committed
(`2388321f1`), but its AC could not be done, so the ticket could not close. Ticket 03 needed 02's
committed code, not its closure, yet would have waited on 02 forever. The commit message of
`fe1da94d1` states it: "The planner only treats a dependency as met when the ticket is status: done,
so 03 -> 04 would wait on 02 forever. 03 needs 02's committed code, not its closure." The edge was
dropped by hand. Then `4650dea80` made 02 depend on 04, because while 02 had no open dependency
"the planner keeps releasing it, and every release ends in a failed completion check that halts the
batch".

**What this adds to the fix direction.** Both shapes are the conflation this entry describes:
`depends_on` means "closed", but the dependants needed "built". A ticket whose phases are all
signed off and whose code is committed should satisfy a code dependency, separately from closure.
Closure should stay gated on the AC store. The planner prompt and `ticket_prioritizer` both need
the distinction, and the generator should emit `expects_from`-derived edges as code dependencies.
Shape 2 also needs the other direction: an AC whose proof needs a later ticket's artifact should
make that later ticket a prerequisite of the closure only, not of the build.

---
