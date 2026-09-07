---
title: "Fix: a plan is not a hand-off — the promise-claim gate stops blocking every newly generated ticket"
date: "2026-09-07"
time: "07:00"
type: manual
components: 
  - build_pipeline
  - commit_guardian
summary: "Fixed a commit gate that demanded a test at the moment a plan was written, which made it impossible to commit any ticket generated from an approved requirement and so broke the documented plan-then-build path end to end."
description: "Commit 508b0363a fixes main() in check_proof_promise_claim.py, which applied its promise-versus-claim comparison to every staged ticket regardless of that ticket's declared state. A ticket at status todo with no implementation was refused for a promised proof whose test is, by this repository's own mandated test-first order, produced in a later phase -- so every ticket generated from an approved AC and carrying a reachability promise could not be committed at all. The parent record BP-1100g-4 already specified the correct trigger in its own criteria (\"When the work is offered for hand-off, then it is refused\"); the shipped code never honoured that clause, so this implements an accepted criterion rather than adding a rule. Only status todo is exempt: in_progress, done, blocked, deferred and any unrecognised value remain checked, because test-writer runs before the coder here and exempting everything-but-done would be a real hole. Absent, unparseable or keyless state is checked, never passed over -- an unreadable state is not evidence of being early. The exemption is reported as a distinct PASSED OVER line so it cannot be mistaken for having been examined and found complete. The promise extraction, claim index, comparison and refusal wording are untouched. Covered by BP-1100g-4-ii and five behavioural tests that execute the deployed hook as a subprocess."
commits: 
  - 508b0363a
breaking: false
---

## Entry

### A gate that asked for the proof before the work had started

`check-proof-promise-claim` refuses work whose plan promised a kind of proof that no
test ever claimed. That rule is right, and it is one of the load-bearing defences
against work being called finished on the strength of a promise.

It was asking at the wrong moment. `main()` read every staged ticket the same way,
with no notion of whether that ticket described work that had started. A ticket
generated from an approved requirement is, by construction, a promise and nothing
else — the tests that claim it are written in a later phase, by a different agent,
because this repository mandates that order. The gate demanded the claim at the exact
moment the promise was written, so the ticket could not be committed at all.

The effect was not narrow. Every ticket generated from an approved requirement that
carried a reachability promise hit the same refusal, which meant the documented
plan-then-build path could not be completed for any of them.

### The accepted criterion already said when to ask

`BP-1100g-4`, the record this gate implements, states the trigger in its own criteria:
*"When the work is offered for hand-off, then it is refused."* The shipped code never
honoured that clause. So this change is not a new exception carved into a rule — it is
the rule, finally applied at the point it always named.

### Two versions of this fix would have been worse than the bug

Exempting everything except finished work is the easy reading and is a genuine hole:
the test writer runs before the coder here, so by the time work is under way the claims
should exist, and skipping them would let real gaps through.

Passing over work whose state cannot be read would be worse still. A missing or
unparseable declaration is not evidence that work is early; treating it as such turns
a parse failure into a free pass. The module already refused to make that trade —
it reports work it cannot read as its own failure rather than as "nothing missing" —
and the new path matches that posture.

Work passed over as still-planned is now named in the output as passed over. Skipping
it silently would have made "not due yet" indistinguishable from "checked and clean",
which is the confusion this whole area exists to prevent.

### How it was verified, and the step that nearly reported the wrong answer

The five new tests run the deployed hook as a real subprocess and were taken through
the full sequence: red against the unmodified hook, green after the fix, red again
with the fix reverted, green once restored.

That third step needed care. Because the tests exercise the *deployed* copy, reverting
the source alone leaves the fixed copy running — the revert would have stayed green,
and that reads exactly like "the test is not actually coupled to the fix". Rebuilding
inside the revert is what makes the check mean anything.

One further detail worth keeping: a plain assertion that started work is still refused
would have passed against the broken code, because the bug was *over*-refusal — the old
gate refused everything. Each of those tests therefore also runs the byte-identical
still-planned sibling as a control and asserts it is passed over. That control is what
makes them fail today, and what stops a fix that merely switches the gate off from
satisfying them.
