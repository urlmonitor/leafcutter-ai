---
title: "KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done"
description: "KI-ACS-016 — There is no retired `work_status`, so a superseded child stays in its parent's `covered_by` and the parent can never be proved done"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-14'
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
- **Occurrences:** 4 (the fourth, 2026-10-12, is the latent block firing on `INF-400c-4`; see Occurrence 4)
- **First seen:** 2026-08-25 · **Last seen:** 2026-10-12
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

## Occurrence 4 — 2026-10-12 (filed 2026-10-14): the latent block fired on `INF-400c-4`

- **Occurrences:** now 4. **Last seen:** 2026-10-12.
- **Severity:** unchanged at medium. The refusal is loud, and the cost is composites held at a
  false `todo`. It is no longer latent: it fired on real work.

**What happened.** On 2026-10-12, flipping `INF-400c-4` to `done` was refused by
`check-done-proof`:

```text
composite INF-400c-4 is marked done but its covered_by children are not all done-and-covered — unproven: INF-400c-4-ii
```

`INF-400c-4-ii` has `req_status: superseded`, `superseded_by: [INF-700c-2]` and `work_status:
todo`. This is the case the "latent, not live" paragraph above predicted.

**Where, on `origin/main` `435c11395`.** Both composite paths still ignore supersession:

- `scripts/ac_store/_done_proof_composite.py:247-262` (`_unproven_composite_children`, the
  pre-commit path that `templates/scripts/commit_guardian/check_done_proof.py:442-455` calls).
  Every AC-id child that is not `work_status: done` goes onto `unproven`. Nothing reads
  `superseded_by` or `req_status`.
- `scripts/ac_store/done_proof.py:1505-1516` (`_resolve_all_child_ids`, used by
  `_verify_composite_eligible` in CI). A superseded child is kept as a leaf that needs a linked
  test.

The store's field has moved since the original filing. Supersession is now
`req_status: superseded` plus `superseded_by`, not `status: superseded_by`. A fix should test
`superseded_by` non-empty or `req_status == "superseded"`.

Reproduced read-only. The origin/main source copy of `_unproven_composite_children`, run on
`INF-400c-4` with `work_status` set to `done` in memory, returns `['INF-400c-4-ii']`. Nothing was
written.

**Blocked composites today.** A read-only scan of the store on `435c11395` ran
`_unproven_composite_children` on every composite that is not itself superseded, as if flipped
to `done`. It then sorted each unproven id into "superseded", "done and waived", or "other".
These 7 composites are refused only because of superseded descendants, and would pass if those
were excluded:

| Composite | `work_status` | Superseded children reported unproven |
|---|---|---|
| `BO-100d` | todo | `BO-100d-1`, `BO-100d-2` |
| `BO-530-3` | todo | `BO-530-3-i` |
| `GE-128a` | todo | `GE-128a-1` |
| `INF-400c-2` | **done** | `INF-400c-2-i` |
| `INF-400c-4` | todo | `INF-400c-4-ii` (this occurrence) |
| `INF-400c-5` | **done** | `INF-400c-5-ii` |
| `TKT-500f-6` | todo | `TKT-500f-6-iii` |

`INF-400c-2` and `INF-400c-5` are already `done`. They will be refused the next time either
file is staged. A further 22 composites have a superseded unproven child as well as other
unfinished children, so supersession is not their only blocker. Among them are `ACD-1800b`,
`ACS-300g`, `BO-2300` / `BO-2300a` (both `done`), `BP-1000a`, `PER-100d` and `TQ-600a`.

No composite is blocked today by the docs-only waiver gap
(KI-CG-20260914-done-proof-precommit-ignores-test-required). PR #1165 fixed it at source. An
`INF-500d-4` refusal on 2026-10-14 came from an install built before that fix (see that entry's
Occurrence 4).

**Fix direction, sharpened.** Use the second option above, with one shared predicate:
`superseded_by` non-empty or `req_status == "superseded"`. Skip such children in
`_unproven_composite_children` and in `_resolve_all_child_ids`. Keep them in `covered_by` for the
audit trail. Keep refusing:

- a composite whose children are all superseded, since that leaves nothing to derive from;
- a non-superseded child that is not `done`.

Add a pre-commit/CI parity test with one superseded child and one done, covered child. After
the fix, the 7 composites above should pass `pre-commit run check-done-proof` when flipped.

**Related.** KI-CG-20260914-done-proof-precommit-ignores-test-required is the sibling exemption
in the same two functions (waived children). It was fixed by PR #1165 without covering
supersession.

---
