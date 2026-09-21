---
title: "KI-CG-20260831-test-ac-tags-dead-three-ways — the test-to-AC traceability gate is registered nowhere, defaults to warn-only, and the config key that would escalate it is absent from the shipped config"
description: "KI-CG-20260831-test-ac-tags-dead-three-ways — the test-to-AC traceability gate is registered nowhere, defaults to warn-only, and the config key that would escalate it is absent from the shipped config"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260831-test-ac-tags-dead-three-ways — the test-to-AC traceability gate is registered nowhere, defaults to warn-only, and the config key that would escalate it is absent from the shipped config

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-31 · **Last seen:** 2026-08-31
- **Where:** `templates/scripts/commit_guardian/check_test_ac_tags.py` —
  `_DEFAULT_ENFORCEMENT_MODE = "warn"`, `_CONFIG_KEY = "test_ac_tag_enforcement"`, `main()`'s exit
  contract

**Symptom.** Pointed at one arbitrary existing test file it finds 20 real violations and reports
success:

```
$ python templates/scripts/commit_guardian/check_test_ac_tags.py \
    unit_tests/commit_guardian/test_check_duplicate_code_strict.py
WARNING: ... is missing a # covers: XX-NNN tag.        (x20)
check_test_ac_tags: 20 warning(s) — add '# covers: XX-NNN' tags to suppress these warnings.
exit: 0
```

**Three independent reasons it can never block.**

1. **Not registered.** Absent from `hooks_manifest`, from the deployed `.pre-commit-config.yaml`,
   and from every CI workflow. (It is one of the orphans in
   `KI-CG-20260831-hook-scripts-never-invoked`; recorded separately because the other two reasons
   would survive registration.)
2. **Warn-only by default** — `_DEFAULT_ENFORCEMENT_MODE = "warn"`, which the module docstring
   frames as a *"grace period"* ending when *"a follow-up ticket flips the default to error
   mode."*
3. **The escalation switch does not exist.** The config key it reads to leave warn mode —
   `test_ac_tag_enforcement` — is **not present** in `commit_guardian.json`. `grep` returns
   nothing. The documented flip is unreachable through config; only `CHECK_TEST_AC_TAGS_MODE` in
   the environment can do it, and nothing sets that.

**Why it matters beyond one dead hook.** `# covers:` tags are how `check_done_proof` and the AC
store connect an AC to the test proving it. A gate meant to keep that mapping honest, which has
never run, means the backfill it waits on has no deadline and no measurement — and 20 violations
is a sample from one file, not the total.

**Fix direction.** Decide whether this gate is wanted. If yes: register it, add
`test_ac_tag_enforcement` to `commit_guardian.json`, measure the real violation count, and set a
date for the warn→error flip. If no: delete it rather than leave a plausible gate a reader will
assume is enforcing.

**Related.** `KI-CG-20260831-hook-scripts-never-invoked` (this is one of the 24).
`KI-CG-021`, `KI-CG-022` (the same defect recorded per-hook).

**Pattern:** a gate that is three separate kinds of off, each of which alone would suffice.

---
