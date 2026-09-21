---
title: "KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done"
description: "KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done"
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

# KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 3
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26
- **Where:** `scripts/ac_store/done_proof.py` / the `check-done-proof` hook; the
  `work_status` enum in the AC store schema

**Symptom.** When an AC is withdrawn (`status: superseded_by` + `superseded_by: [<id>]`),
the store has no matching resting value for `work_status`. The enum offers
`not_started` / `todo` / `in_progress` / `done` / `null` and nothing that means *retired*.
`done` is no longer true; `todo` is false in the other direction.

The parent is the sharper half. `check_done_proof` reads the parent's `covered_by`, and
the convention — followed consistently across the store — is to **leave the withdrawn
child listed**, preserving the audit trail. Once the parent is marked `done`, that child
must be accounted for, and both routes are closed:

- no `# covers:` tag for the withdrawn child → the parent fails with "uncovered children";
- add one → it is a dangling tag, because the child's `status` is no longer `active`.

**Current instances.** `INF-400c-4` still lists `INF-400c-4-ii`, and `INF-400c-5` still
lists `INF-400c-5-ii`; both children were withdrawn 2026-08-26. `INF-400c-2` lists
`INF-400c-2-i`, withdrawn 2026-08-25.

**It is latent, not live — and that is the trap.** `INF-400c-4` and `INF-400c-5` are both
`work_status: todo`, so the gate does not fire on them today; it fires on whoever
eventually finishes that work. `INF-400c-2` is already `done` with a withdrawn child and
passes, because these hooks validate only the files present in that commit's index — the
parent was staged before the child was withdrawn, and nothing rechecks the store
afterwards. So the store contains a passing composite whose proof set no longer holds, and
two more that will block on a future commit for a reason unrelated to the work in it.

**Do not fix by stripping the child from `covered_by`.** That trades a blocked gate for a
lost audit trail and diverges from the store-wide convention, leaving no record that the
parent ever had that child. The workaround used on `INF-400c-2-i` — setting
`work_status: null` — is also not a considered state; it was chosen because nothing better
existed, and it is recorded as a workaround in that record's own `it_requirements`.

**Fix direction.** Either add a real `retired` (or `superseded`) value to the `work_status`
enum and teach `done_proof` to discharge such children, or teach `done_proof` to skip any
`covered_by` entry whose record has `status` starting with `superseded` — the same
predicate `scan_ac_store.py`'s `exclude_superseded` already applies when building the
ready queue. The second is smaller and reuses a rule the store already trusts. Note the
scanner and the gate currently disagree about supersession: the scanner understands it
(verified — neither withdrawn AC appears in `ready` or `blocked`), the gate does not.

**Numbering note.** This entry was drafted as `KI-ACS-014` on 2026-08-26 and renumbered on
filing: `014` and `015` were taken by unrelated branches that merged in the interim. The
changelog entry `2026-08-26-1125-…` and the commit message of `04dfdba5` both cite the
draft number `KI-ACS-014` and should be read as pointing here.

**Related.** `KI-ACS-004` (`mark_ac_done.py` leaves `covered_by`/`implemented_by` empty —
the same proof set, corrupted from the writing side). `KI-KM-009` (the supersessions that
surfaced this). The "AC-store commits — stage the parent alongside the child" rule in
`CLAUDE.md`, which explains why the `INF-400c-2` instance passes.

---
