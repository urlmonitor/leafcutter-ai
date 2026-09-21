---
title: "KI-ACS-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them"
description: "KI-ACS-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them"
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

# KI-ACS-20260907-approved-code-acs-with-no-test-contract-sit-on-main-until-something-stages-them

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 2 confirmed (`UXP-600a`, `TQ-100c-2-i`); the store has not been swept
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `templates/scripts/commit_guardian/_ac_schema_validators.py` —
  `validate_test_contract`, and the staged-file scoping it inherits

**Symptom.** `validate_test_contract` refuses an approved code AC that declares no
`test_spec`. It is a **forward ratchet**: it evaluates only the records present in the current
commit's index. A record that was approved before the rule shipped, and has not been re-staged
since, carries the violation indefinitely and is reported by nothing.

`TQ-100c-2-i` on `origin/main`:

```
level: L3
readiness: approved
assigned_agent: python-coder
change_target: code
                        <- no test_spec, no test_required
```

Title: *"An AC marked done with zero covering tests is flagged by the integrity check."* An
approved code AC, specifying an integrity check, with no test contract — sitting on the default
branch, unflagged.

**How it surfaced, which is the instructive part.** Nobody went looking. A separate change
corrected an unrelated false claim in that record's `it_requirements`. Editing the file staged
it; staging it put it in front of the ratchet for the first time since the rule existed; CI
failed. **The defect was found by an edit that had nothing to do with it.**

That makes the true population unknown. Two are confirmed only because two records happened to
be touched. `UXP-600a` (`change_target: schema`, `frontend-coder`) slipped the same way and is
additionally `readiness: reviewed`, which the ratchet also scopes out.

**Why medium and not high.** The direction is safe — these are unproven records, not falsely
proven ones, and the ratchet does close over anything actively worked on. It earns a place in
the register because the *population is unmeasured* and because each instance surfaces at the
worst moment: as a CI failure on an unrelated PR, where it reads as "this change broke
something" rather than "this change revealed something."

**Remediation.**

1. **Sweep the store out of band** and count. Until that number exists, every estimate of the
   AC store's health is an estimate of the staged subset. This is the whole remediation as far
   as knowing the problem goes.
2. Decide the disposition per record — write the contract, or reclassify honestly to non-code.
   Note the reclassification path is the tempting wrong answer when the record genuinely
   specifies code, which `TQ-100c-2-i` does.
3. Consider a whole-store run of this specific rule on push to main, in the shape of the
   existing `AC store valid (whole store, push to main)` job, so the backlog is a number that
   moves rather than a series of ambushes.

**Related.** `KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks`
(above) — the reason a local pass does not surface these either.
The CLAUDE.md note under "AC-store commits — stage the parent alongside the child", which
documents the same staged-scope blindness for a different pair of fields.

**Pattern:** a forward ratchet is a promise about new work, not a statement about the store —
and its silence about old work is easy to read as a clean bill of health.

---
