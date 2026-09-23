---
title: "KI-ACD-019 — `goal_to_epic.py` cites two governing acceptance criteria that do not exist, and five `done` ACs in this register's scope are falsified"
description: "KI-ACD-019 — `goal_to_epic.py` cites two governing acceptance criteria that do not exist, and five `done` ACs in this register's scope are falsified"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-23'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-019 — `goal_to_epic.py` cites two governing acceptance criteria that do not exist, and five `done` ACs in this register's scope are falsified

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **partially fixed, 2026-09-23.** The falsified-`done`-ACs half is resolved:
  all six records named below have been reconciled against the store (five reopened to
  `work_status: todo`, one — `BO-1500f-1` — legitimately re-verified and re-marked
  `done` under `AC_ENFORCE_STRICT=1`). The other half — `goal_to_epic.py` and
  `epic_naming.py` citing `ACD-1200a-6`/`-7`, which still do not exist in the store — is
  unchanged and still reproduces; a commit as recent as 2026-09-21 touched these exact
  lines without correcting the citation. See "Re-verified 2026-09-23" below. Kept open
  for the citation half.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `scripts/ac_store/epic_naming.py` (`:9`, `:24`, `:178`, `:186`, `:305`, `:351`) plus `scripts/goal_to_epic.py` (`:59`, `:321`) citing `ACD-1200a-6`; three further sites citing `ACD-1200a-7`

**Ticket:** [`tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md`](../../tickets/00_inbox/TICKET-20260825-BuildOrchestrationPhantomTriage.md)

**Symptom — the part that is not in any other entry.** `scripts/goal_to_epic.py` names
`ACD-1200a-6` **six times** and `ACD-1200a-7` three times as the acceptance criteria governing
its behaviour. **Neither id exists anywhere in the AC store.** Verified: a store-wide search
for `^id: ACD-1200a-6` and `^id: ACD-1200a-7` returns nothing, while
`grep -c "ACD-1200a-6" scripts/goal_to_epic.py` returns 6.

Their siblings `ACD-1200a-4` and `-5` were re-parented to `ACD-1200g-1`/`g-2` on 2026-06-17
with `amended_by` notes recording the move. `-6` and `-7` left no record and no supersession
note.

So the two behaviours those citations govern — `KI-ACD-011` (phrase-unaware epic-name
truncation) and `KI-ACD-012` (Master_Plan frontmatter missing fields the commit gate requires)
— are not merely uncovered. **The code asserts it is governed by criteria that were deleted.**
That is a `GE-122`-class citation-resolving-to-zero-records instance sitting inside the file
this register describes, and it is worse than an ordinary gap: a reader who checks whether the
behaviour is specified finds a citation and stops looking.

**Five `done` ACs falsified.** The same triage found `BO-2200c-5`, `BO-202`, `BO-2300a-1`,
`BO-2300a-2` and `BO-1500f-1` marked `done` with criteria the code does not satisfy; the
per-record evidence is in the ticket. `ACD-1200a-3-iii` is a sixth, and is this component's
own: it claims "the derived folder name contains only ASCII alphanumeric characters", and
`_to_pascal_case('Ship parts tree — the fast path, quickly')` returns
`'ShipPartsTreeTheFastPath,Quickly'` — reproduced inside the criterion's own `Given`. Its three
covering tests all assert `result.isascii()`, which is `True` for a comma.

**Two of these are one bug.** `KI-ACD-005` and `KI-ACD-006` both follow from a single decision
in `plan-feature.js:2057-2097` — an agent's reply is accepted as a user's decision — and both
ACs went `done` against it in the same ticket. Fixing either half alone leaves the other
false. Likewise `KI-ACD-004` and `KI-ACD-009` are both `{{config.output_root}}` resolving
relative to the session cwd, and both halt `/plan-feature` before triage.

**A correction to `KI-ACD-012`, which names the wrong gate.**
`templates/hooks/ticket_frontmatter_guard.py` is a Claude Code `PreToolUse` hook on
`Edit|Write`, not a pre-commit hook. A `Master_Plan.md` written by `goal_to_epic.py` through
Python file I/O never passes through the Edit/Write tool, so that guard never fires on
generation. The gate that actually runs at commit time is `check_doc_frontmatter.py`, whose
`ticket_frontmatter.required_fields` is `["title", "status", "components", "created",
"depends_on"]`. The generator emits `status`, `components` and `created` — so **two** fields
are missing at the real gate, not six. The defect and the fix direction are right; the
mechanism and the number are not.

**A correction to `KI-ACD-002`'s counters.** `Occurrences: 1` / `First seen: 2026-08-18`
undercounts by a week and at least four tickets. The identical verbatim blocker is recorded on
three tickets under `tickets/99_done/EPIC-BuildAcResolvesALeafAcsConnectedBuildSet/`, all
`created: '2026-08-11'`, and one of them shows the hand-repaired pipe form — so the manual
workaround had been applied at least three times before the 2026-08-18 sighting.

**Scope note.** The triage covered `KI-ACD-001` through `KI-ACD-012`. Entries `-013` onward
were filed after it ran and are **not** triaged.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M1 for the tests that let these read
`done`; the missing-citation half is its own shape — a reference that resolves to nothing reads
as coverage to everyone who checks for one.

**Re-verified 2026-09-23.** Checked both checkable factual claims against the current
store and current code, not the entry's own narrative.

**Citation half — still true.** `grep -rn "ACD-1200a-6\|ACD-1200a-7"
scripts/goal_to_epic.py scripts/ac_store/epic_naming.py` still returns the citations
(`goal_to_epic.py:59-60,321,329`; `epic_naming.py:9,24,178,186,305,351`). A store-wide
search for `^id: "ACD-1200a-6"` / `^id: "ACD-1200a-7"` still returns nothing — neither
id exists. `git log -L` on `goal_to_epic.py:59,60` shows the block was rewritten as
recently as `fb07b48d` ("refactor(ac-store): split goal_to_epic.py into 14 modules,
and cover 8 previously-untested ACs", PR #844, 2026-09-21) — the citations were kept
and given bracket annotations (`[epic_naming]`, `[epic_master_plan, epic_phases]`)
rather than corrected. The code still asserts it is governed by criteria that do not
exist.

**Falsified-ACs half — resolved.** Checked `work_status` on all six named records
directly:

| AC | `work_status` now | Note |
|---|---|---|
| `BO-2200c-5` | `todo` | reopened |
| `BO-202` | `todo` | reopened |
| `BO-2300a-1` | `todo` | reopened |
| `BO-2300a-2` | `todo` | reopened — its own notes narrate the `KI-ACD-006` reopening and record (as of 2026-09-08) that the PT-gate fix was "observed... incidentally" but "unverified" against the mid-gate site; `KI-ACD-006`'s own 2026-09-23 closure independently confirms the code now satisfies this AC at all three sites, but the store has not been flipped back — a separate, not-yet-done step |
| `ACD-1200a-3-iii` | `todo` | reopened (this component's own) |
| `BO-1500f-1` | **`done`** | re-marked `done` on 2026-09-23 via commit `9f783a26` (part of PR #865, closing `KI-ACD-009`), using `scripts/ac_store/mark_ac_done.py` after re-running `AC_ENFORCE_STRICT=1 python -m pytest unit_tests/workflows/test_bo_1500f_1.py unit_tests/workflows/test_bo_1500f_1_real_registry_read.py -q` → **8 passed** with the xfail mask off. This is a legitimate, rigorously re-verified `done`, not a repeat of the falsification — see `docs/known-issues/ac-driven-dev/resolved/resolved-blocker-ki-acd-009.md`'s own 2026-09-23 closure note for the full chain of evidence. |

None of the six is currently a falsified `done`. The falsified-ACs half of this entry
is resolved; only the missing-citation half keeps it open.

---
