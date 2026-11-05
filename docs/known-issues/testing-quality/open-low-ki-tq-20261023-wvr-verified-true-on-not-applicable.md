---
title: "KI-TQ-20261023-wvr-verified-true-on-not-applicable — the wrong-version verdict reads applicable: false together with verified: true when covering tests exist but none is in scope"
description: "low — scripts/build_orchestration/_wvr_verdict.py assemble sets verified = bool(rows) and not unfinished and not reason_override, without looking at applicable. wrong_version_runner.py _execute's NO_TESTS_OUTCOME branch passes the not_in_scope rows with applicable=False, so the verdict reads applicable: false and verified: true. The no-source branch passes no rows and reads verified: false. This contradicts the stated intent that a not-applicable verdict is never reported as verified (TQ-500g-1-v, TQ-500g-5). Harmless today: no reader uses verified."
type: reference
category: reference
status: active
created: '2026-10-23'
last_updated: '2026-10-23'
components:
  - testing_quality
related_docs:
  - docs/known-issues/testing-quality.md
  - docs/known-issues/README.md
  - docs/reference/wrong-version-runs.md
---

# KI-TQ-20261023-wvr-verified-true-on-not-applicable — a not-applicable verdict can say verified

> Filed 2026-10-23. Index: [testing-quality.md](../testing-quality.md).
> Filename severity is the three-level index bucket (`low`); the original grading is the
> `**Severity:**` line below.

- **Severity:** low. No decision reads `verified` today, so nothing is passed or stopped wrongly.
  It is a wrong field in a contract other code may start to trust.
- **Status:** open, no AC. Documented as a known limit in `docs/reference/wrong-version-runs.md`
  (TQ-500g-5, not yet on `origin/main`).
- **Occurrences:** 1 (found in the TQ-500g-5 reference review, 2026-10-23).
- **First seen:** 2026-10-23 · **Last seen:** 2026-10-23
- **Where** (code line numbers at `origin/main` `ae3a1591c`):
  - `scripts/build_orchestration/_wvr_verdict.py`:114-143, `assemble`. :140 sets
    `"verified": bool(rows) and not unfinished and not reason_override`. The `applicable` argument
    (:114, :122) is copied into the verdict but not used in `verified`.
  - `scripts/build_orchestration/wrong_version_runner.py`:280-296, `_execute`.
    - No source AC (:282-283): `assemble([], applicable=False, outcome=NO_SOURCE_OUTCOME)`. No
      rows, so `verified` is false.
    - Covering tests exist but none is in scope (:291-294): `out_rows` holds one `not_in_scope` row
      per out-of-scope test (:291), and `assemble(out_rows, applicable=False,
      outcome=NO_TESTS_OUTCOME)` (:294) gets non-empty rows and no unfinished ones, so `verified`
      is true.
  - The intent it breaks: `TQ-500g-1-v.yaml`:33-34 ("the runner's own not-applicable outcome in
    its outcome, never \"verified\"") and :229-230 ("Never record \"verified\" for it"), under
    `docs/acceptance-criteria/testing-quality/TQ-500-checks-that-can-fail/`. On this branch
    (TQ-500g-5, commit `5437ab6ec`) `TQ-500g-5.yaml`:255 states it directly: "A not-applicable
    verdict is never reported as verified."
  - Why it is harmless today: `scripts/commit_guardian/check_build_epic_gate_verdicts.py`:131-135
    reads only `gate_passed` and `applicable`. The other `verified` readers
    (`_fl_heavy_lane_gate.py`, `build-feature.js`, `build-ticket.js`) read other verdicts, not this
    one.

## Symptom

`wrong_version_runner.py` (or `wrong_version_gate.py finish`) prints
`{"gate_passed": true, "applicable": false, "verified": true, "outcome": "wrong-version runs not
applicable: no covering test declares a wrong version or the discrimination angle", ...}` with
`not_in_scope` rows in `results`.

## Detection

Run the runner for an AC whose covering tests exist but declare no wrong version and no
discrimination angle. `applicable` is false and `verified` is true.

## Workaround

Read `applicable` before `verified`. Treat `verified` as meaningless when `applicable` is false.

## Suggested fix

Directions only; nothing here is applied.

- In `_wvr_verdict.py`:140, add `and applicable` to the `verified` expression.
- Add a test for the NO_TESTS branch that asserts `verified` is false.
- Update `docs/reference/wrong-version-runs.md` in the same change. On this branch it documents
  the current behaviour twice: the output description (:121, "It can also be true on a
  not-applicable verdict that lists `not_in_scope` rows") and the Known limits row (:266). Both
  must go when the fix lands.

**Pattern:** a derived flag computed from the rows alone, next to a flag that says the rows do
not count.
