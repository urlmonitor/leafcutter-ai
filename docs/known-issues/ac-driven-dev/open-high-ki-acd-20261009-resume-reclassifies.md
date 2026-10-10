---
title: "KI-ACD-20261009-resume-reclassifies — a resumed /plan-feature run asks the product-truth classifier again, gets a different answer, and silently drops the owner's answer at the product-truth gate it was paused at"
description: "high — on resume the product-truth phase dispatches the classifier again instead of reusing the paused run's decision. The classifier is not deterministic. The same request came back full-set on the first run and mockup-only on the resume, so the mock-data stage left the run set, the owner's edit at the mock-data gate was never applied, and the run moved on to the mockup gate without saying so. Ticketed in the plan-feature resume ticket filed 2026-10-08."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - ac_driven_dev
  - ux_prototyping
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261009-resume-reads-own-drafts-as-orphans.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
---

# KI-ACD-20261009-resume-reclassifies — a resumed /plan-feature run asks the product-truth classifier again, gets a different answer, and silently drops the owner's answer at the product-truth gate it was paused at

- **Severity:** high. The owner answers one gate and the run acts on a different decision.
  Nothing in the run's output says the answer was dropped: the run just pauses at the next
  gate. An owner who approves that next gate commits product truth built without the change
  they asked for.
- **Status:** open. Ticket: `TICKET-20261008-PlanFeatureResumeKeepsItsClassification`
  (`tickets/00_inbox/`, PR #1065). It brings the product-truth gates in line with ACD-2100c-3
  (done), which already holds for the AC gates. No AC of its own.
- **Occurrences:** 1 (2026-10-08: first run `wf_fc30286f-e12`, resume `wf_424216d0-185`).
  Session observation. The mechanism below is traced in code.
- **First seen:** 2026-10-08 · **Last seen:** 2026-10-08
- **Where:** `templates/workflows-js/plan-feature.js`, line numbers verified on origin/main
  `c79d41e34` (identical on this branch):
  - the `pt-classify` dispatch, with no resume check (:2760-2769);
  - the run set derived from that answer (`derivePtRunSet`, :1086, called at :2778);
  - the product-truth gate's pause context, which is only `{ stage: ptStep.stage }` (:2870);
  - `resolveGate()` (:1642), which matches a resume answer only on an equal gate id (:1650) and
    otherwise falls through to `pauseAtGate()` (:1808).

  The classifier rule is at `templates/agents/pt-classifier.md:92-94`; its model pin is at `:14`.

## Symptom

The same request, run twice:

| run | kind | classifier outcome | what happened |
|---|---|---|---|
| `wf_fc30286f-e12` | first run | `full-set` (flow, mock data, mockup) | `mock-data-author` drafted; the run paused at `pt-gate-mockdata` |
| `wf_424216d0-185` | resume; the owner's answer was an edit with feedback at `pt-gate-mockdata` | `mockup-only` (no flow, no mock data) | the mock-data stage was not in the new run set, so the edit was never applied; `mockup-author` ran; the run paused at `pt-gate-mockup` |

The second answer is not only different, it is wrong. The request explicitly extends an existing
flow, and the classifier's own rule counts "an extension of an existing journey" as a flow
(`pt-classifier.md:92-94`).

## Mechanism

1. An ADR-024 resume is a fresh invocation, so every `agent()` call runs again. The
   product-truth phase dispatches `pt-classifier` at its start without asking whether this is a
   resume (:2760-2769), and derives the stage list from the new answer (:2778).
2. Nothing of the paused run's classification survives to be reused. The gate's pause context
   holds only the stage name (:2870).
3. `pt-classifier` is a Haiku-pinned prompt (`pt-classifier.md:14`). Two dispatches on one
   request are not guaranteed to agree, and here they did not.
4. `resolveGate()` applies the resume answer only when its gate id equals the gate being resolved
   (:1650). The new run set never reaches `pt-gate-mockdata`, so the answer never matches. The
   run reaches `pt-gate-mockup`, falls through to `pauseAtGate()` (:1808), and overwrites the
   run's pause record. `scripts/pause_store.py` keeps one record per run id (`write_record`,
   :96-147), so the answered gate leaves no trace.

**Sibling gap at the same seam (traced in code, not observed).** The AC loop skips re-authoring
on a resume that moves past its gate (`peekPausedGateId` :1596, read at :3130-3132,
`skipAuthorOnResume` :3134, from ACD-2100c-3 and ACD-2100c-3-i). The product-truth loop
(:2803-2939) has nothing similar. On an approve resume it re-dispatches the stage's author before
resolving the gate, so it commits a draft the owner never saw.

## Detection

A resumed run whose resume answer names a product-truth gate (`pt-gate-mockdata`,
`pt-gate-mockup` or `pt-gate-flow`) and which pauses at, or ends after, a different gate without
re-dispatching that stage's author with the feedback. Compare the `pt-classify` outcome in the
first run's journal with the resume's. Any difference means the run set changed under the
answer.

## Workaround

Drive the product-truth stages by hand, and commit each approved stage under the workflow's own
subject, `plan-feature(MOCK-DATA|MOCKUP|FLOW): <component>`. The resume's committed-stage scan
(`scanCommittedStages`, :824; check at :2805) recognises those subjects and skips the stages
(UXP-549). Used on 2026-10-08 and 2026-10-09 on branch `ac-authoring/ux-prototyping` (commits
`e7c04e5f8`, `46255a446`, `ae3dd8c16`).

## Fix direction

The ticket's, in short:

1. Persist in the gate's pause context the classifier decision, the ordered stage list, the
   paused stage and the artifact paths its author reported.
2. On a resume, take the decision from the record and do not dispatch `pt-classifier`.
3. Skip the paused stage's author unless the answer is edit; on approve, commit the recorded
   paths unchanged.
4. When a resume answer names a gate the run is not paused at, stop with a distinct status
   that names both gates, instead of pausing somewhere else.

Classifier accuracy is out of the ticket's scope apart from one eval row for a flow extension.
Once the resume stops asking twice, the classifier does not have to be deterministic for this
defect to close.

**Related.** `KI-ACD-20261009-resume-reads-own-drafts-as-orphans`, a second resume defect that
fires earlier in the same workflow. `KI-BO-20260907-resume-replays-cached-resolver`, a different
resume mechanism.

**Pattern:** a resume that recomputes a non-deterministic decision instead of reading back the
one the owner answered against.
