---
title: "KI-BO-20260907-0850 — `build-ticket.js` is the declared twin of the driver just fixed: one defect is unfixed there and the other handler is a generation behind, so `/build-ticket` still loses the ticket in ways `/build-feature` no longer does"
description: "KI-BO-20260907-0850 — `build-ticket.js` is the declared twin of the driver just fixed: one defect is unfixed there and the other handler is a generation behind, so `/build-ticket` still loses the ticket in ways `/build-feature` no longer do"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-20260907-0850 — `build-ticket.js` is the declared twin of the driver just fixed: one defect is unfixed there and the other handler is a generation behind, so `/build-ticket` still loses the ticket in ways `/build-feature` no longer does

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** **RESOLVED** (6124e025, PR #687 — squashed follow-up commit "close the twin
  divergence — build-ticket.js gets both dispatch fixes (BO-3701, BO-3000)"; verified 2026-09-25
  by reading `build-ticket.js` on main and running the BO-3701 / BO-3000 twin tests). See
  Resolution below.
- **Occurrences:** 0 observed on this path; the twin defect was observed 3× on `build-feature.js`
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `templates/workflows-js/build-ticket.js` — the per-ticket phase loop at `:1258`
  (`for (const currentPhase of neededPhases)`) and the handoff branch · twin of
  `templates/workflows-js/build-feature.js`
  <br>The handoff branch is deliberately cited without a line number: it moves whenever either
  half is edited, so a number there rots. The loop line is stable and is the one to grep.

**Symptom.** PR #687 fixed two dispatch defects in `build-feature.js`: the frozen phase list
(`BO-3700`) and the handoff contract (`BO-3000a`). `build-ticket.js` received neither.

**Corrected 2026-09-07, same day as filing.** The first version of this entry said the twin
"carries **both** defects unchanged". That overstates one half and the precision matters,
because the two halves need different remedies:

- **Frozen phase list — genuinely unfixed.** `build-ticket.js:1258` is still
  `for (const currentPhase of neededPhases)` over a list computed once before any phase runs.
  No AC covers it: `BO-3700`'s criteria name `build-feature.js` explicitly.
- **Handoff routing — present, but a generation behind.** The twin DOES have a handoff branch
  and DOES read `handoff_target`; that arrived with `BO-3000`, whose test file already drives
  this driver. What it lacks is everything `BO-3000a` added: `handoff_target` declared in
  `PHASE_RESULT_SCHEMA`, the conditional `if`/`then` requirement, and the two-case diagnosable
  refusal. So this half is a divergence between twins rather than an absent guard.

That second half is already covered by an acceptance criterion, and the criterion is now
false. `BO-3000` requires:

> Then build-ticket.js MUST apply the same handoff routing behaviour as build-feature.js, so
> the two drivers cannot diverge

The drivers diverged the moment `BO-3000a` landed on one of them. `BO-3000` still reads
`work_status: todo`, so nothing has to be authored to justify fixing this half — the
requirement exists and is violated.

Its handoff refusal still reads, verbatim, the pre-fix wording:

```text
named no recognizable handoff_target ('undefined')
```

Its `PHASE_RESULT_SCHEMA` has no `handoff_target` property and no conditional requirement, and
its phase loop is still `for (const currentPhase of neededPhases)` over a list computed once
before any phase runs.

**Why this is a register entry rather than a TODO.** The two files declare themselves twins.
`build-feature.js`'s own header says so:

> TWIN: The phaseOrder array and per-ticket phase loop below are the canonical twin of
> build-ticket.js Phase 1–3. Keep them in sync manually — any change to build-ticket.js
> phaseOrder or the retry/adjudication logic must be mirrored here.

"Keep them in sync manually" is the whole mechanism. There is no test asserting the twins agree,
so divergence is invisible until someone runs the neglected one. PR #687 widened the gap
deliberately and said so in both AC records — the reason given (no red baseline for
build-ticket.js in that pass, and widening a fix to a second driver without one turns a fix into
a rewrite) is sound, but it is a reason to file this, not a reason to forget it.

**Who is exposed — and the two halves differ, which changes the triage order.** The first
version of this entry said "anyone running `/build-ticket`". That is true of the HANDOFF half
and over-general for the other:

- **Handoff divergence — reachable on every drive.** Any coder that hands off to test-writer
  hits it, and that is a routine, template-mandated path. This is the half an operator meets
  first.
- **Frozen phase list — reachable only when the drive contains a promoting phase.** The
  promotion comes from `architect-review`, so a standalone ticket that never schedules
  `architect-review` cannot hit it at all.

Severity is unchanged — `BO-3700`'s field evidence was 2 of 4 tickets in a single batch — but
the handoff half is the more reachable one and should be fixed first. The original wording
would have led a triager to the opposite order.

The "0 occurrences" figure is therefore partly sampling and partly a real difference in reach:
the incidents that motivated #687 all came from an epic drive, which uses `build-feature.js`.

**The templates already assume the fix is universal.** `python-coder.md` and `test-writer.md`
now instruct agents to return `handoff_target` unconditionally, without reference to which
driver dispatched them. Checked: `build-ticket.js`'s schema sets no `additionalProperties:
false`, so the extra field is ignored rather than rejected — harmless, but it means an agent
correctly emitting the field under this driver still gets refused, which is the worst
combination for diagnosis. The operator sees a conformant agent rejected for non-conformance.

This paragraph belongs entirely to the HANDOFF half, i.e. to `BO-3000`. Nothing in `BO-3701`
covers it. A reader who lands `BO-3701` and closes this entry on that basis will leave the
more reachable of the two defects in place.

**Countermeasure — now two independently schedulable pieces, not one pass.** The first version
of this entry said "mirror both changes in the same pass". That framing is stale, and it is
worth correcting precisely because it is the framing that produced the divergence in reverse:

- **Handoff half** — covered by `BO-3000`'s existing twin criterion, still `work_status: todo`.
  Nothing to author.
- **Frozen-list half** — covered by `BO-3701` (authored 2026-09-07), a top-level L2 rather than
  a child of `BO-3700`, because `BO-3700` is now `done` and hanging a `todo` child under it
  would recreate the done-parent-with-unfinished-children drift this repo swept for.

Either can land alone without leaving the other unrecorded. Doing both in one branch is an
efficiency, not a constraint.

A NAIVE MIRROR WOULD INTRODUCE A BUG. `build-ticket.js` is not a copy of its twin, and two of
`BO-3701`'s criteria exist because of that:

- Its `canonicalPriority` (`:251-264`) deliberately does NOT throw on a name outside
  `phaseOrder` — it returns `phaseOrder.length` and warns. So an unknown promoted name fed into
  a re-derived pending set does not get ignored; it sorts LAST and runs *after commit and
  pull-request*. `BO-3700`'s wording ("ignored rather than dispatched") is adequate for
  `build-feature.js` and under-specified here.
- The driver sets `lastRecord = null` on an unreadable read-back (`:1358-1363`). Once the
  pending set is derived FROM that reply, "unreadable" silently becomes "nothing left to run"
  unless the criterion forbids it — a failure mode the fix itself creates.

**What would have caught the divergence.** A test asserting the two drivers agree. `BO-3701`
takes the cheap half: its promotion cases must be asserted over every entry in
`H.TWIN_DRIVERS`, which the harness already exposes and which at least seven existing test
files already loop over. The general parity gate — asserting the two `phaseOrder` arrays and
handoff branches agree — is deliberately NOT in `BO-3701`: it also serves `BO-3000`'s half, so
parking it there would make one record's `done` depend on work two records need, and it carries
a real design question (assert the arrays literally equal, or the observable orderings equal?).
It wants its own id.

**Pattern:** `docs/reference/false-green-mechanisms.md` → a duplicated implementation kept
consistent by a comment. The comment is not a mechanism.

**Related.** `KI-BO-20260901-1000` and `KI-BO-20260901-1052` (the two defects, as observed and
fixed on the other twin). `KI-BO-20260901-0920` (a third control ADR-006's flattening dropped —
the same refactor is upstream of all of these).

## Resolution (verified 2026-09-25)

Both halves were fixed on `build-ticket.js` in the same squash-merge that fixed the other twin:
6124e025 (PR #687). That squash includes a follow-up commit, "close the twin divergence —
build-ticket.js gets both dispatch fixes (BO-3701, BO-3000)", which references this KI. This
entry was filed from an earlier state of that branch and was never closed. `git log -S` confirms
that `const pendingPhases`, `absorbPromotedPhases` and `handoff_target: {` all entered
`build-ticket.js` in 6124e025.

Checked against current `main` (d2fe85a1):

- **Frozen phase list — fixed.** The loop is now `while (pendingPhases.length > 0)` over a
  work-list (`const pendingPhases = [...neededPhases]`, ~`:1429`). After every dispatch,
  `absorbPromotedPhases()` re-derives the work-list from the read-back and re-sorts it by
  canonical priority. Both naive-mirror pitfalls are handled:
  - A name outside `phaseOrder` is skipped rather than sorted last.
  - An unreadable read-back returns `[]` and leaves the pending set as it was.
- **Handoff — fixed.** `PHASE_RESULT_SCHEMA` (~`:98-152`) now declares `handoff_target` and has
  the `if: {status: const 'handoff'} / then: {required: ['handoff_target']}` conditional. The
  handoff branch has two refusals that can be told apart: (a) no target, and (b) a named target
  that is not in `phaseOrder`, with the value quoted verbatim. The pre-fix wording
  `named no recognizable handoff_target` occurs 0 times in the file.

Test evidence:

- **Blocked on Windows as the repo stands.** `python -m pytest
  unit_tests/workflows/test_bo_3701_build_ticket_dispatch.py
  unit_tests/workflows/test_bo_3000_handoff_routing.py
  unit_tests/workflows/test_bo_3000a_3700_dispatch_defects.py -q` gives 11 failed / 20 passed.
  The failures are the same at 6124e025 itself, so this is not a regression.
- **Cause: the test harness, not the driver.** `_driver_harness.write_ticket_record` writes in
  text mode, so on Windows the ticket files get CRLF line endings. The mjs harness's
  `/^---\n/` frontmatter regex then fails to match, and the read-back reports no
  `needed_phases`.
- **Probe with the harness patched to write LF.** The probe copied main into a scratch folder
  and changed only the harness's `open(..., newline="\n")`.
  - `test_bo_3701_build_ticket_dispatch.py` and `test_bo_3000_handoff_routing.py`:
    **15 passed, 7 subtests passed**. This covers promotion dispatch, unknown-name exclusion,
    unreadable read-back, cross-twin parity over `H.TWIN_DRIVERS`, and both handoff refusal
    cases on `build-ticket.js`.
  - The 3 tests still failing in `test_bo_3000a_3700_dispatch_defects.py` drive
    `build-feature.js`, not this driver. They fail on Windows path separators and CRLF in a
    test-appended ticket body, so they are also fixture artifacts.

Not done by this fix: the general twin-parity gate for `phaseOrder` and the handoff branch, which
this entry noted "wants its own id". The Windows CRLF problem in the harness is a separate
testing defect and is not tracked here.

---
