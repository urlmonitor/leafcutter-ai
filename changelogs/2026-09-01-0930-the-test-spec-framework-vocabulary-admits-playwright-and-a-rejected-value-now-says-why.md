---
title: "The test_spec framework vocabulary admits playwright, and a rejected value now says why"
date: "2026-09-01"
time: "09:30"
type: manual
components:
  - ac_store
summary: "Widens the test_spec framework enum to admit playwright, and un-buries the diagnostic so a rejected value names itself and lists the accepted members."
description: "config/ac_store_schema.json held enum ['unittest', 'pytest'] for test_spec[].framework, which refused the playwright value two approved BP-1400 records declare for a headless route-render check. That failed validate_ac_schema across the whole build_pipeline component, so the documented bulk pre-flight for it could not go green. Also restructures test_spec's oneOf wrapper, which was swallowing the enum diagnostic and leaving authors with no way to learn the allowed values."
commits:
  - 9a638d52b
breaking: false
---

## Entry

**A vocabulary that refused something the project ships.** `test_spec[].framework` accepted
only `unittest` and `pytest`. `BP-1400c-1` and `BP-1400c-1-i` — both approved, both priority
high — declare `framework: playwright` for a check that headlessly loads every web-app route,
and the package ships a Playwright-driven `webapp-testing` skill. The records were right and
the enum was wrong.

The blast radius was larger than two records. `validate_ac_schema.py` over
`docs/acceptance-criteria/build_pipeline` failed outright, which meant the bulk pre-flight
this repository's own guidance prescribes before a finalization drive could not go green for
that component — on any branch, for a reason belonging to none of them.

**A second defect, found while fixing the first.** Widening the enum satisfied half the
criterion. The other half — that an unshipped value is still refused, *and the diagnostic
names it and lists the accepted members* — kept failing. `test_spec` was declared as
`oneOf: [<array>, <null>]`, and that combinator swallows the nested reason, surfacing only
`is not valid under any of the given schemas`. The allowed values never reached the author.
That is very likely how two approved records came to sit in the store unvalidatable in the
first place: the schema knew what was wrong and would not say.

Restructured to `type: ["array", "null"]` with `minItems`/`items` applied directly —
semantically identical, since JSON Schema no-ops those on a non-array instance — and the real
message now surfaces: `'jasmine' is not one of ['unittest', 'pytest', 'playwright']`.

**The enum stays closed.** Three named values, no catch-all, no relaxation to a bare string.
A fix that deleted the enum would have made the accepted-half test pass while destroying the
property the field exists to enforce, which is why the covering test asserts both halves and
why the criterion says so explicitly.

**Evidence.** Mutation-proven rather than merely green-after-red: red before the fix, green
after, red again with the fix stashed, green again on restore. `test_check_ac_schema.py` is
61 passed. The component that could not validate now reports **all 597 AC YAML files valid** —
that command is the reason this was worth doing, and the count is quoted because a run
resolving to zero files exits reporting success.

**A latent cap violation surfaced and was recorded.** Staging the parent for a `covered_by`
back-link pulled `ACS-100a` into `check_ac_limits` for the first time, which blocked the
commit: 6 L2 children against a cap of 5, no waiver, pre-existing. The hook validates the
staged set rather than the store, so a parent nobody stages is a parent nobody counts. Added
`child_limit_override: 6` recording the count that already existed — not headroom, and a 7th
child must re-justify. The honest fix is a Pattern C split; the waiver makes the debt visible
instead of latent until then.
