---
title: "KI-ACS-20260909-standalone-validator-does-not-derive-declares-side-effect — `validate_ac_schema.py` passes records the commit hook then rejects, so a clean bulk run is not evidence on every field"
description: "medium — no wrong data reaches the store, because the commit hook does catch it. The cost is that the documented pre-flight (\"validate the whole set in bulk so violations surface at once rather than as a serial per-commit cascade\") does not"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260909-standalone-validator-does-not-derive-declares-side-effect — `validate_ac_schema.py` passes records the commit hook then rejects, so a clean bulk run is not evidence on every field

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium — no wrong data reaches the store, because the commit hook does catch it. The cost is that the documented pre-flight ("validate the whole set in bulk so violations surface at once rather than as a serial per-commit cascade") does not actually surface this class, so you get exactly the serial cascade the pre-flight exists to prevent — and, worse, a `OK: all N valid` that a reader will reasonably treat as complete.
- **Status:** open — no AC.
- **Occurrences:** 1 observed, on 12 records in one commit
- **First seen:** 2026-09-09, authoring the `INF-1200` tree · **Last seen:** 2026-09-09
- **Where:** `scripts/ac_store/validate_ac_schema.py` versus `templates/scripts/commit_guardian/check_ac_schema.py` (the BO-2900g-2 `declares_side_effect` derivation)

**Symptom.** Fifteen new AC records were authored with `declares_side_effect: true` on twelve of them. `python scripts/ac_store/validate_ac_schema.py docs/acceptance-criteria` reported:

```text
OK: all 4008 AC YAML files are valid.
```

The very next `git commit` was blocked by `check-ac-schema` with twelve findings of the form:

> `declares_side_effect is authored as True but this AC's own Then clause derives False — the two disagree.`

**Mechanism.** `declares_side_effect` is a DERIVED field: BO-2900g-2 requires the authored value to agree with what the record's own Then clauses imply. That derivation lives in the commit-guardian hook. The standalone validator checks schema shape — types, required fields, enum membership — and does not run the derivation, so an authored value that contradicts the criteria is structurally invisible to it.

Neither tool is wrong on its own terms. The problem is that they are *documented as the same check at different times*: `CLAUDE.md`'s "AC-store hygiene — bulk pre-flight" section tells you to run the validator specifically so hook violations surface early, and for this field it cannot.

**Why this is worth an entry rather than a shrug.** This is the fourth time a documented defence in this repo has turned out to be narrower than it reads — after `feedback_categories.yaml`'s wrong path, the validator's own bare-directory no-op (`KI-ACS-001`), and the stale-`origin/main` merge audit. The shape is identical every time: **a check that examined less than you thought looks exactly like a check that found nothing wrong.** `OK: all 4008 ... valid` states its N precisely so you can tell it looked — but N counts files parsed, not properties checked.

**Fix direction.** Either have the standalone validator import and run the same derivation the hook uses (one shared helper, so the two can never diverge again), or amend the `CLAUDE.md` pre-flight section to state plainly which classes it does NOT cover. The first is better; the second is the honest minimum and should not be skipped if the first is deferred. Do not "fix" this by dropping the hook check — the hook is the one doing the real work.

**Related.**
- `KI-ACS-001` — the same script, the same class of over-trust (a bare directory argument validated zero files and exited 0 for eight days).
- `docs/reference/false-green-mechanisms.md` — this is an instance of the "checked less than claimed" family.

**Pattern:** two tools documented as one check, where the cheaper one is silently narrower and is the one the runbook tells you to run first.

---
