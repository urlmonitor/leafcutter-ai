---
title: "KI-BO-026 — Work the planner never selected is reported as work \"added to the epic after the plan was fixed\""
description: "KI-BO-026 — Work the planner never selected is reported as work \"added to the epic after the plan was fixed\""
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
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
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
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

---
