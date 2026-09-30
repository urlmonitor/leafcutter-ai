---
title: "A journey never confirmed is now named as such instead of silently skipped (UXP-700c-2-i)"
date: "2026-09-17"
time: "00:00"
type: manual
components:
  - ux_prototyping
summary: "The product-truth checker's freshness check now names, on its existing warning channel, every journey that has no confirmation record at all -- previously it skipped such journeys in total silence, which was indistinguishable from a checker that had examined them and found nothing wrong."
description: "Ticket 22 (UXP-700c-2-i) of EPIC-TruthfulProjectRecord was finished by hand from the halted /build-feature run at the user's direction (no ticket-supervisor or test-writer dispatch; python-coder wrote the tests itself, test-first). Its precondition, UXP-700c-2's freshness verdict (ticket 21), had already landed on main via PR #833 by the time this ticket was picked back up, resolving the blocker test-writer recorded against it. Established exactly what was missing against the AC's four clauses before writing anything: _check_freshness's pre-existing `if not confirmed: continue` already satisfied 'not reported as up to date' (never added to verdicts with a current value), 'not reported as behind' (never added with a behind value either -- the key is omitted entirely), and 'excluded from compared' (the counter increments after that continue). Only 'reported as never confirmed, naming the journey' was genuinely missing -- the checker skipped such journeys in total silence, which is indistinguishable, to a reader who does not know the vocabulary, from a checker that examined them and found nothing wrong -- exactly the vacuous-pass failure GE-120 exists to name. Wrote three tests first (two direct-call, one real-subprocess-CLI reachability test per the ticket's own REQUIRED entry), confirmed two red for the missing report and one already green for the pre-existing exclusion, then added one line -- `warnings.append(f\"[freshness-never-confirmed] {flow_id}: never confirmed\")` inside the existing `if not confirmed:` branch, immediately before its `continue` -- reaching the same warnings channel every other freshness/pointer finding already uses, never a new one. Net +1 content line (398 -> 399 of the 400-line ratchet); no file split needed. Mutation-tested: reverted the one line, confirmed the two guarding tests went red again for the same reason, restored, confirmed green. Running the full unit_tests/product_truth suite surfaced one pre-existing over-broad assertion in test_uxp_700c_2.py (`warnings == []` for a never-confirmed journey) that predated this AC and was stale relative to it (test drift, not production drift: that test's own stated purpose, per ticket 21's Test Requirements, was the compared/verdicts accounting only) -- narrowed to assert no behind-prefixed warning is present, leaving its verdicts/compared assertions untouched. Suite: 128 passed / 11 subtests passed (was 125 before, +3 new tests). Real store: validate_product_truth.py exits 0, checked-and-sound, all 14 real journeys individually named never-confirmed (today's actual migration state, matching the AC's own notes), \"compared 0 journey(s) for freshness\", and zero journey-file churn in git status both before and after. Updated docs/product-truth/README.md's Validation section and docs/how-to/authoring-product-truth-artifacts.md's Part 6, both of which previously said a never-confirmed journey 'is skipped entirely'; left docs/reference/product-truth-checker-outcomes.md untouched since it documents only the unrelated run-level four-value outcome vocabulary."
commits:
breaking: false
---

## Entry

Ticket 22 (`UXP-700c-2-i`) of `EPIC-TruthfulProjectRecord` was finished by hand
from the halted `/build-feature` run, on branch `feature/uxp-700c-2-i` off
`origin/main`, at the user's direction.

**A never-confirmed journey is now named, not silently skipped.**
`_check_freshness` already excluded a journey with no `confirmed` record from
`verdicts` and from the `compared` figure — that already satisfied "not
reported as up to date," "not reported as behind," and "excluded from
compared." What was missing was the journey actually being *named*: the
checker said nothing about it at all, which reads identically, to anyone who
does not know the vocabulary, to a journey that was checked and found sound.
Fixed with one line: a `[freshness-never-confirmed] <journey id>: never
confirmed` warning, appended to the same `warnings` list every other
freshness/pointer finding already feeds — no new reporting channel.

Three tests were written first, in a new
`unit_tests/product_truth/test_uxp_700c_2_i.py`, reusing
`_uxp_700c_2_fixtures.py`'s existing builders: two direct-call tests against
`_check_freshness`, and a required reachability test running the real
`validate_product_truth.py` CLI as a subprocess. Two started red (the missing
report, both at the direct-call and the CLI level); the third — never current,
never behind — was already green, confirmed and reported as pre-existing
rather than claimed as new work. The one-line fix was mutation-tested:
reverted, confirmed the two red tests go red again for the same reason,
restored, confirmed green.

Running the full `unit_tests/product_truth` suite surfaced one pre-existing,
now-stale assertion in `test_uxp_700c_2.py` (`warnings == []` for a
never-confirmed journey) that predates this AC — a test-drift case, not a
production defect: that test's own stated purpose (ticket 21's own Test
Requirements) was only ever the compared/verdicts accounting, never the
warnings channel. Narrowed the one over-broad assertion (now asserts no
behind-prefixed warning is present) rather than touching production to keep
a stale assertion green.

Suite: 128 passed / 11 subtests passed (was 125 before this ticket). Real
store: `validate_product_truth.py` exits 0, `checked-and-sound`, all 14 real
journeys individually named never-confirmed — the documented day-one
migration state — `"compared 0 journey(s) for freshness"`, and zero journey
file churn in `git status` before or after. `docs/product-truth/README.md`
and `docs/how-to/authoring-product-truth-artifacts.md` updated; both
previously described the never-confirmed case as being "skipped entirely,"
which was true of the report but not of the underlying accounting, and is
no longer true of either.

`agents.python-coder` and `agents.test-writer` are marked `signed_off`;
`test-runner`, `ac-validator`, `ac-fulfillment-gate`, `documentation-expert`,
`documentation-verifier`, `pr-reviewer` and `commit` are left `needed` —
those phases were not actually re-dispatched in this by-hand pass, matching
this project's established by-hand-completion precedent.
