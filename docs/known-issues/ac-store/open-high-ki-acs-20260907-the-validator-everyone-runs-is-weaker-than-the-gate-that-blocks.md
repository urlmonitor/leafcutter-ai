---
title: "KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks"
description: "KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks"
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

# KI-ACS-20260907-the-validator-everyone-runs-is-weaker-than-the-gate-that-blocks

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1 observed directly; the exposure is every AC-store change ever verified locally
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `scripts/ac_store/validate_ac_schema.py` versus
  `templates/scripts/commit_guardian/check_ac_schema.py:619`

**Symptom.** Two tools validate AC YAML. Everything in this repository — CLAUDE.md's own
"AC-store hygiene" pre-flight, every agent instruction, every sign-off — reaches for the
standalone one. The required CI gate runs the other. **They do not apply the same rules.**

```
$ grep -n validate_test_contract scripts/ac_store/validate_ac_schema.py
                                        (no match)
$ grep -n validate_test_contract templates/scripts/commit_guardian/check_ac_schema.py
619:    errors.extend(validate_test_contract(path, data))
```

So a run reporting

```
OK: all 3820 AC YAML files are valid.
```

is a genuine pass of a **strictly weaker** rule set than the one that decides whether the
commit lands. The count is real, the files were read, nothing is broken — and the result still
does not answer the question the operator asked it.

**Observed.** During the 2026-09-07 census work, an agent amended six records, ran
`validate_ac_schema.py` across four components, reported four clean runs each naming a nonzero
count, and pushed. CI then failed the required `AC store valid` check on
`validate_test_contract` — a rule the local tool cannot see. The local verification was
performed correctly and proved the wrong thing.

**Why this is high.** It is not a missing check; it is a check that *reports success in the
vocabulary of the check you wanted*. The output is indistinguishable from the stronger run, so
there is no signal to investigate, and the divergence is invisible until a PR is already open.
Every agent in this repository currently has a green-looking local gate that under-tests
relative to CI, and CLAUDE.md prescribes it by name.

**Remediation.** Either make `validate_ac_schema.py` call the same validator set as
`check_ac_schema.py` — one rule set, two entry points — or make its output state which rule
set it ran and that it is not the gate. The first is better: two tools that answer "is this AC
valid?" differently is the divergence, and documenting the divergence preserves it. If they
must stay separate, a parity test asserting the validator list is identical would at least
fail when they drift again.

**Related.** `KI-ACS-001` (the same script's bare-directory no-op — the second time this file
has looked like it checked something it did not).
`docs/reference/false-green-mechanisms.md` → M9, and `unit_tests/README.md` §8.

**Pattern:** two implementations of the same question, one of which is the gate and the other
of which is the one everybody runs.

---
