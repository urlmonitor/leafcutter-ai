---
title: "KI-BO-026 — Work the planner never selected is reported as work \"added to the epic after the plan was fixed\""
description: "KI-BO-026 — Work the planner never selected is reported as work \"added to the epic after the plan was fixed\""
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-12'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-026 — Work the planner never selected is reported as work "added to the epic after the plan was fixed"

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open · AC **BO-300d** (authored 2026-08-26, `readiness: draft`), whose criteria
  were amended on the same day precisely because the first draft demanded an attribution the
  run cannot make. See the 2026-08-31 note on KI-BO-025 for why: the baseline this compares
  against is the plan, not the epic.
- **Occurrences:** 2 (2026-08-25; run `wf_54e15913-aea`, 2026-10-12, 39 tickets mislabelled — see
  "Observed again, 2026-10-12")
- **First seen:** 2026-08-25 · **Last seen:** 2026-10-12
- **Where:** `templates/workflows-js/build-feature.js` — `compareEpicTicketSets()`
  (deployed `~:1838`) and `epicRecheckReport()` (deployed `~:1952`)

**Symptom.** `compareEpicTicketSets` computes

```js
additions: currentOpen.filter((p) => plannedPaths.indexOf(p) === -1)
```

— every ticket that is open at completion time and was not in the plan. That correctly caught
the 20 tickets of KI-BO-025 and correctly set `epic_complete: false`, which is the right
verdict and worth keeping.

But `epicRecheckReport` then files them under the field `discovered_after_planning` with the
action text:

> "This work was added to the epic after the plan for this drive was fixed, so it was never
> built."

That is false. All 20 tickets were committed to the epic folder before the drive was launched;
none was added during it. They were never *added* — they were never *selected*.

**Why the distinction matters.** The two causes have opposite remedies. Work genuinely added
mid-drive is a scope question — someone changed the epic under a running build, and the
sensible response is to find out who and decide whether it belongs. Work the planner skipped is
a tooling question with no one to ask. A reader following the message as written goes looking
for a change that never happened, and the real defect (KI-BO-025) stays invisible behind an
explanation that sounds complete.

The remedy sentence happens to be right — "re-run /build-feature to plan and build it" is
exactly what KI-BO-025 requires — but it is right by accident, for a stated reason that does
not hold.

**Fix direction.** The comparison already has both inputs needed to tell these apart: a ticket
present in the epic folder at *plan* time but absent from `plannedPaths` was skipped, while one
absent at plan time and present at completion was added. Capture the plan-time folder listing
and split `additions` into `never_planned` and `added_during_drive`, with the right remedy on
each. Until then the field name asserts a cause the code cannot actually determine.

> **Review note, 2026-08-26 — that paragraph contradicts itself, and its second half is the
> true one.**
>
> "The comparison already has both inputs needed" and "Capture the plan-time folder listing"
> cannot both hold: the second sentence is an instruction to *create* an input, which concedes
> the first is wrong. Nothing in the data flow carries a plan-time folder listing today.
> `plannedPaths` is what the planner *selected*, which is the value in dispute, and the
> completion-time listing is read fresh at the end. There is no snapshot of what was on disk
> when planning ran, so from what the code currently holds the two causes are genuinely
> indistinguishable.
>
> This matters for whoever picks it up. "The inputs are already there" implies a ten-minute
> change that reads two existing variables; the real work is a new value captured at plan time
> and threaded through to the completion comparison. Anyone starting from the optimistic
> reading will hunt for a plan-time listing, fail to find one, and have to re-derive this.
>
> The rest of the entry is sound and should stay intact — the distinction between "never
> selected" and "added mid-drive", the observation that the two have opposite remedies, and the
> note that the remedy sentence is right by accident are all correct, and are the valuable part.
> Only the "already has both inputs" clause needs striking.
>
> One design question the fix should settle rather than inherit: a plan-time snapshot can itself
> be stale or absent on a resumed or cached run. Decide up front what `additions` reports when
> the snapshot is missing. The honest answer is probably a third bucket meaning "cannot
> determine" rather than a silent fallback to either existing label — falling back is how the
> current fabricated cause arose in the first place.

**Pattern:** a correct verdict delivered with a fabricated cause.

## Observed again, 2026-10-12

**Where:** `/build-feature` on EPIC-RightJobRightAgent (48 tickets), run `wf_54e15913-aea`.
Line numbers are `templates/workflows-js/build-feature.js` at `b6249edd3`. The run executed
that template.

**What the run reported.** `discovered_after_planning` named 39 tickets, with the same action
text: "This work was added to the epic after the plan for this drive was fixed". The message
then counted "47 piece(s) of work in total were not built". Every one of the 39 was committed in
the scaffold commit before the drive began. **The fabricated cause misled diagnosis exactly as
this entry predicts.** The operator first read the report as "the epic planner dropped 39
tickets from its plan" and looked for a planner defect.

**What the planner actually did.** It was correct. Look 1 returned `batches` holding 9 tickets
(5 + 2 + 2) and `enumerated` holding all 48. The 9 are exactly the 9 tickets whose `depends_on`
is empty. Each of the other 39 depends on at least one ticket that was not done at look 1. For
example, `02_…ACD-1600c-1-i` depends on `01_…ACD-1600c-1`, which was in batch 1 and halted.
Withholding them is BO-100e-1's design: a later layer is offered at a later look. The planner
prompt (:3074-3091) has no size or format limit. `PLANNER_SCHEMA` (:60-115) has no `maxItems`.
`BATCH_SIZE = 12` (:2987) only chunks the dispatch of one batch. It does not cap the plan.
There was no look 2 because the run stopped after batch 1 on staged leftovers
(`KI-BO-20261009-one-halted-ticket-stops-the-whole-epic-run`, occurrence 2026-10-12).

**The 2026-08-26 review note's premise no longer holds, and the cheap fix is now available.**
That note says "Nothing in the data flow carries a plan-time folder listing today". BO-100e-1
has since added one. `PLANNER_SCHEMA.enumerated` (:110) is the folder's full contents at each
look. The look loop freezes look 1's value as `runSetPaths` (:3051, :3109-3125), whose own
comment calls it "the run set, frozen". It is used only by the first-look run-set lock, which
admits a later look's offers (:3180-3187). The completion-time comparison still receives
`plannedTicketPaths`, the set of tickets actually *released* in batches, at both call sites:
the empty-plan return (:3246-3248) and the final return (:3565-3566). So "enumerated at look 1
but never released" is filed as an addition. This run had a 48-entry run set and used none of
it for the report.

**Fix, restated against today's code.** Pass `runSetPaths` into the completion comparison.
Split `additions` three ways:

- in the run set but never released: `not_reached`, with the halts or the stop as the reason;
- absent from the run set: `added_during_drive`, which keeps today's wording;
- run set unknown (`runSetUnknownLooks`, :3058, non-empty): `cannot_determine`, as the
  review note asks.

The verdict (`epic_complete: false`) is right in all three cases and should stay. A side
finding: the comment on `runSetUnknownLooks` (:3054-3057) says it is "Reported on the payload
so a degraded drive says so". It is never reported. The variable is written (:3123) and never
read, so a drive that ran under the unsound fallback looks identical to a sound one.

---
