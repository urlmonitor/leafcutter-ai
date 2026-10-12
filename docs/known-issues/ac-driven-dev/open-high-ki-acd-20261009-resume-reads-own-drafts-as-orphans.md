---
title: "KI-ACD-20261009-resume-reads-own-drafts-as-orphans — a resumed /plan-feature run stops at the partial-run recovery prompt and offers the paused run's own reviewed drafts as orphans from a crashed session, and every answer to that prompt undoes the review"
description: "high — the orphan pre-flight runs before anything checks for a resume, so the drafts a paused AC stage left on disk for review qualify as orphans. In run wf_c7c29412-79a the owner's edit for the BA gate was set aside and the run paused at the orphan prompt, listing the 16 UXP-591 drafts the owner had just reviewed. Yes commits them under a subject the stage scan does not recognise, discard deletes them, and no aborts. No ticket of its own; the resume ticket must cover it."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/ac-driven-dev/open-high-ki-acd-20261009-resume-reclassifies.md
  - docs/known-issues/ac-driven-dev/open-low-ki-acd-20260927-po-origin-agent-defeats-partial-run-recovery.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
---

# KI-ACD-20261009-resume-reads-own-drafts-as-orphans — a resumed /plan-feature run stops at the partial-run recovery prompt and offers the paused run's own reviewed drafts as orphans from a crashed session, and every answer to that prompt undoes the review

- **Severity:** high. The owner's answer for the gate the run is paused at is set aside, and the
  prompt that replaces it is false: it calls the drafts "uncommitted AC files from a prior
  session". None of its three answers applies the owner's answer. `yes` leads the run to
  re-author the stage the owner just reviewed, `discard` deletes the reviewed drafts, and `no`
  aborts.
- **Status:** open. No AC and no ticket of its own.
  `TICKET-20261008-PlanFeatureResumeKeepsItsClassification` (PR #1065) **must cover it**, or a
  sibling ticket must. That ticket's AC-5 (an unmatched resume answer is reported, not dropped)
  is scoped to the product-truth gates, and this pre-flight runs before the product-truth phase,
  so the ticket as written does not reach it.
- **Occurrences:** 1 (2026-10-09, run `wf_c7c29412-79a`, resumed with an edit answer for
  `gate-ba` on the ux-prototyping authoring run). Session observation. The mechanism below is
  traced in code.
- **First seen:** 2026-10-09 · **Last seen:** 2026-10-09
- **Where:** `templates/workflows-js/plan-feature.js`, line numbers verified on origin/main
  `c79d41e34` (identical on this branch):
  - the Partial-Run Recovery pre-flight (:2576-2637), which calls `scanOrphanedAcDrafts()` (:600)
    and its gate `resolve-orphans-choice` (:2587-2618) with no resume check;
  - the orphan qualifier: an authoring-agent `origin_agent` and `readiness: draft` (:695-698);
  - the `yes` path, `resolveOrphanedDrafts()` (:901), which commits with stage key `recovery`
    (:916-924);
  - the committed-stage scan (`scanCommittedStages`, :824; its stage table at :856-863 and the
    subject match at :870), which knows PO, BA, IT-PO and the three product-truth stages only.

## Symptom

Run `wf_c7c29412-79a` was a resume carrying the owner's edit answer for `gate-ba`. Before it
reached the BA stage it paused at `resolve-orphans-choice`, listing the 16 UXP-591 ACs. The paused
run had drafted those itself, and the owner had just reviewed them at `gate-ba`. The prompt
described them as uncommitted files "from a prior session".

## Mechanism

1. A paused AC stage leaves its drafts uncommitted on purpose. The BA writes them, the run pauses
   at `gate-ba`, and the stage commit happens only after approval.
2. On the resume, a fresh invocation, the pre-flight runs right after worktree setup (:2578),
   before the committed-stage scan (:2642) and long before the AC loop's resume check
   (`peekPausedGateId`, read at :3130-3132). It lists modified and untracked AC YAML files and
   keeps those whose `origin_agent` is `product-owner`, `business-analyst` or `it-po` and whose
   readiness is `draft` (:695-698). The BA template writes `origin_agent: business-analyst`
   (`templates/agents/business-analyst.md:724`), so the paused run's own drafts qualify.
3. The resume answer names `gate-ba`, not `resolve-orphans-choice`, so `resolveGate()` does not
   match it (:1650). It falls through to `pauseAtGate()` (:1808) and overwrites the run's single
   pause record (`scripts/pause_store.py`, `write_record` :96-147). The `gate-ba` answer is gone.
4. What each answer does next:
   - **yes** commits the drafts through `commitStageOutput(..., "recovery", ...)` (:916-924). Its
     subject is `plan-feature(RECOVERY): ...` (`stageDisplayName`, :253-263). The stage scan's
     table has no `recovery` entry (:856-863), so the BA stage is not seen as committed and the
     business-analyst runs again over the reviewed drafts.
   - **discard** deletes the drafts, tracked or untracked (:941 onward).
   - **no** aborts the run.

**Not every resume trips it, and why is not established.** On 2026-09-27 a `gate-ba` resume in
run `wf_a2fd1222-f54` continued to the BA stage commit
(`KI-BO-20260928-pause-verify-rejects-an-enveloped-read-back`). The pre-flight reads each
candidate file through a `status-checker` dispatch and skips any file whose read fails or does not
parse (:666-686). Drafts whose `origin_agent` is a person's name are skipped too
(`KI-ACD-20260927-po-origin-agent-defeats-partial-run-recovery`). Either could explain that pass.
Any AC-gate resume whose drafts do qualify should hit this.

## Detection

A resumed run whose resume answer names `gate-po`, `gate-ba` or `gate-itpo` and which pauses at
`resolve-orphans-choice`. Compare the listed AC ids with the drafts the paused run reported at its
gate. If they are the same set, the "orphans" are the run's own drafts.

## Workaround

Do not answer the orphan prompt. Apply the owner's answer by hand: re-dispatch the stage's author
with the feedback, or edit the drafts directly. Then commit the stage under the workflow's own
subject (`plan-feature(BA): <component>`) so the next resume's stage scan skips it. Used on
2026-10-09 for the UXP-591 BA edit (commit `d600877aa` on branch `ac-authoring/ux-prototyping`).

## Fix direction

1. Make the pre-flight resume-aware. When the run carries a resume answer and the pause record
   exists, exclude the drafts the paused run reported, or skip the pre-flight altogether. This
   needs the AC gate's pause context to keep the paused stage's AC ids, which `_resumedContext`
   already reads for the AC loop (:1711-1714).
2. Never let a gate the owner did not answer overwrite the record of the gate they did answer.
   This is the same rule as the resume ticket's AC-5, applied to every gate rather than only the
   product-truth ones.
3. If recovery does commit drafts, use a subject the stage scan maps to the drafts' stage, or
   record the recovered stage some other way the scan reads.

**Related.** `KI-ACD-20261009-resume-reclassifies` (the product-truth resume defect; same ticket).
`KI-ACD-20260927-po-origin-agent-defeats-partial-run-recovery`, the opposite error in the same
qualifier: genuine orphans that it fails to offer back.

**Pattern:** a crash-recovery check that cannot tell a crash from a deliberate pause, because
both leave the same uncommitted files and only the pause record knows the difference.
