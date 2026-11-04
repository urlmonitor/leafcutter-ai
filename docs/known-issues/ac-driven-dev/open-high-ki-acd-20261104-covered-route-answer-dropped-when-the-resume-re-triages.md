---
title: "KI-ACD-20261104-covered-route-answer-dropped-when-the-resume-re-triages — resuming /plan-feature at covered-route-gate runs triage again; when the new triage picks another route, the person's answer is never applied and nothing says so"
description: "high — ACD-2100c-3-iv restores the paused route on resume for every gate except covered-route-gate (plan-feature.js:2353-2355), so that resume re-dispatches ac-triage. On run wf_6207f8a0-8ee the person answered 'amend' (channel person); the new triage returned 'behavioral' instead of 'covered', the covered gate was skipped (:2385), the BA authored 11 records on a route the person had not chosen, and the run's result never mentioned the unapplied answer. The covered-route pause record stayed on disk and was later read back as the gate-ba pause."
type: reference
category: reference
status: active
created: '2026-11-04'
last_updated: '2026-11-04'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/how-to/resume-a-paused-plan-feature-run.md
  - docs/architecture/adrs/ADR-024-interactive-pause-resume.md
  - docs/known-issues/build-orchestration/open-high-ki-bo-20261022-pause-persist-failed-at-gate-ba-in-a-maker-workspace.md
---

# KI-ACD-20261104-covered-route-answer-dropped-when-the-resume-re-triages — resuming at covered-route-gate runs triage again, and an answer for a gate the new route never reaches is silently dropped

> Filed 2026-11-04. Index: [ac-driven-dev.md](../ac-driven-dev.md).

- **Severity:** high. A decision the person made, sent with `channel: "person"`, was not carried
  out. The run went on to a stage the person had not chosen, and its result said nothing about
  the dropped answer. Nothing was lost on disk, and here the new route happened to be a
  reasonable one, but whether the answer applies depends on a second, non-deterministic triage.
- **Status:** open. No AC. Traced to code.
- **Occurrences:** 1 (`/plan-feature` run id `pf-entry-pause-20261104`: paused at
  `covered-route-gate` on workflow run `wf_59d7a401-0f3`, resumed with `amend` on
  `wf_6207f8a0-8ee`, 2026-11-04)
- **First seen:** 2026-11-04 · **Last seen:** 2026-11-04
- **Where:** `templates/workflows-js/plan-feature.js` at base `c4bcf1c14`:
  - `:2353-2355`: `_resumedCtx` is set only when the paused record's `gate_id !==
    "covered-route-gate"`. For a covered-route pause it is `null`.
  - `:2357`: with `_resumedCtx` null, `ac-triage` is dispatched again.
  - `:2385`: the covered gate runs only `if (route === "covered" && ...)`. Any other route
    skips it, so the `resume_answer` for `covered-route-gate` is never looked at.

## Symptom

1. First run: triage returned `covered` (ACD-2100b-5, -i, ACD-1300e-3, -3-i) and the run paused
   at `covered-route-gate`.
2. The person chose `amend`. The run was resumed with
   `resume_answer: {gate_id: "covered-route-gate", action: "amend", channel: "person"}`.
3. The resumed run's triage returned `route: "behavioral"`, `parent_l1_id: "ACD-1300e"`.
4. The BA was dispatched and wrote 11 new records. The run then paused at `gate-ba`.
5. The result carried no mention of the `amend` answer. It was found only by reading the
   journal.

## Mechanism

1. **Re-triage on purpose.** ACD-2100c-3-iv keeps the paused route for every gate except the
   covered one. The covered gate's answer can change the route ("amend" routes as technical),
   so the record's `route: "covered"` is not restored.
2. **But nothing pins the route the answer was given for.** Triage is an LLM classification of
   the same request. The second triage said "Both defects are edge cases on existing ACD-2100b
   and ACD-1300e behaviour" and chose `behavioral`. The covered gate is then never reached, so `resolveGate("covered-route-gate",
   ...)` never runs, the answer is never validated or applied, and no "answer not applied"
   result is produced.
3. **The covered record is left behind.** The clear runs only inside `resolveGate()` for the
   gate it resolves, so `paused_runs/<run_id>.json` still named `covered-route-gate`. At
   `gate-ba` the pause write was declined (KI-BO-20261022). The read-back found that old record,
   `exists: true` passed the check at `:1787`, and the run reported "paused at gate-ba"
   with a record that named a different gate. ACD-1300e-2's it_requirement ("the read-back
   verify confirms the record now names the new gate_id") covers that half and is not built
   yet.

## Detection

A resume supplied for `covered-route-gate` whose journal shows a `stage-0-triage` result with a
route other than `covered`, followed by authoring dispatches.

## Workaround

Read the resumed run's triage result before trusting the outcome. If the route changed, put the
choice to the person again at the next gate. On 2026-11-04 the person approved the BA's
records at `gate-ba` knowing the `amend` answer had been dropped.

## Fix direction

1. On a covered-route resume, restore `route: "covered"` and `existing_acs` from the record and
   skip the second triage, the same way every other gate is resumed. Apply the answer
   (`amend` → technical with the recorded ids, `force` → strategic, `cancel` → cancelled).
2. If triage must run again, any `resume_answer` the run did not consume has to end the run
   with a result that names the unapplied answer and the gate it was for, never a silent
   continue.
3. Clear (or overwrite) the covered-route record once its answer is applied, and make the
   pause read-back check the record's `gate_id` (ACD-1300e-2).
