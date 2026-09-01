---
title: "A missing seam answer is now reported by name, and the hook that reports it actually runs"
date: "2026-08-31"
time: 1810
type: manual
components: 
  - build_pipeline
  - commit_guardian
  - testing_quality
summary: "The reader for BP-1100g-5's cross-layer seam answer ships, reporting absent, reasonless and answered-more-than-once by name — and registering the hook it lives in, which had been deployed and documented but never invoked."
description: "Implements BP-1100g-5-i, completing BP-1100g-5 as a composite. A mechanical reader over the sign-off completion_manifest reports the three non-conforming states of cross_layer_seam_answer by name, while a reasoned not_applicable and a ticket carrying no manifest at all (halted run, or pre-epoch legacy sign-off) are both left unreported. The reader extends _signoff_parity_checks.py rather than adding a second ticket parser. Critically it also registers check-ticket-signoff-parity in commit_guardian.json under its documented id: that hook script was deployed, and documented in the commit-guardian README as live with --enforce, and named by no entry line, so the host this AC pins its reader to reported to nobody. Building the reader without registering it would have produced exactly the inertness the AC's own it_requirements warn against. The four tests were falsified by mutation before being trusted, and the mutation proof itself needed two attempts — the first injected the leak into templates/ while the tests import the build output, so it silently did not land and reported green. That trap is filed as KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy."
breaking: false
---

## Entry

`BP-1100g-5` shipped the *producer* earlier today: every hand-off now carries exactly one
`cross_layer_seam_answer` in its sign-off `completion_manifest`. Nothing read it. This is the
reader, and with it `BP-1100g-5` becomes done as a composite — its falsifiable half is here.

Three non-conforming states are reported **by name**: `absent`, `reasonless`,
`answered_more_than_once`. Two states are deliberately silent: a reasoned `not_applicable`,
and a ticket carrying no `completion_manifest` at all — a run that halted before hand-off, or
a pre-epoch legacy sign-off. Those two are not shortfalls, and reporting them would be the
false-alarm failure the criterion explicitly forbids, because a false alarm has exactly one
natural remedy: weakening the check until it stops.

The reader extends `_signoff_parity_checks.py`. It is not a second ticket parser.

## The hook it lives in was never registered

`check_ticket_signoff_parity.py` existed, was deployed, and was documented in the
commit-guardian README as hook id `check-ticket-signoff-parity` *"with `--enforce`"*. It was
named by no `entry:` line anywhere, so it never ran. This change registers it under that
documented id.

That mattered more than a tidy-up: this AC pins its entire reader onto that host. Building the
reader without registering it would have produced a reader reachable from nothing — the exact
inertness its own `it_requirements` name (*"a reader that is not reachable from a registered
hook is inert"*). The wider finding, that 19 scripts are named by no entry line at all, is
`KI-CG-20260831-hook-scripts-never-invoked`, with criteria already authored under `BP-100n-4`.

## The mutation proof needed two attempts, and the first one lied

The negative control here is the clause *"record W is not reported, because a reasoned negative
is a valid answer."* That clause is green on arrival by construction, so a red baseline cannot
exist for it and the only available evidence is a mutation proof.

Injecting the leak it forbids — making a conforming `result: not_applicable` report as a
shortfall — left **all four tests passing**. That is the exact shape of a dead negative
control, and it would have been written up as the sixth occurrence of `KI-TQ-010`.

It was not. The mutation had been applied to `templates/scripts/commit_guardian/`, while the
tests import the build output at `scripts/commit_guardian/`. The injection never reached the
code under test. Re-run against the deployed copy:

| target | result |
|---|---|
| `templates/…` (source) | 4 passed — proves nothing |
| `scripts/…` (deployed, what the tests load) | **3 failed**, 1 passed |

The record-W clause failed with precisely the right message, and the one test that stayed green
is correct to: it counts answers per work item and does not judge the reasoned-negative rule.
Run time is the secondary tell — 0.24s versus 33.5s, because the deployed hook subprocess only
does real work once findings appear.

The trap is filed as `KI-TQ-20260831-mutation-probe-lands-in-the-wrong-copy`. It is worth its
own entry because it **fails green**: a mutation that does not land is indistinguishable from a
test that cannot fail, so it manufactures a false positive for the very defect the proof exists
to detect. Believing the first result would have meant "fixing" four tests that were already
correct.
