---
title: "KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run"
description: "KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-25'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** **RESOLVED** (registered by `243b6489` / PR #635, GE-122d-6; CI stage added by
  `8cc9fe3c` / PR #682, GE-122d-1; code itself merged via `e429421e` / PR #495; verified
  2026-09-25 by grepping the registry, pre-commit config and CI on `origin/main`, running the
  deployed hook entry, and a green targeted pytest run — see Resolution)
- **Original status (2026-08-18):** open — the code was not on `main`;
  `check_identifier_uniqueness.py` lived only on the then-unmerged PR #495.
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `templates/scripts/commit_guardian/check_identifier_uniqueness.py`;
  `templates/scripts/commit_guardian/commit_guardian.json`; `.pre-commit-config.yaml`

**Symptom.** Found in review round six, by the first reviewer to test the gate *as deployed*
rather than by invoking it from the source tree. Nothing invokes it:

```
grep "check_identifier_uniqueness" templates/scripts/commit_guardian/commit_guardian.json  -> 0
grep "check_identifier_uniqueness" .pre-commit-config.yaml                                 -> 0
grep -rl across every .json / .yaml / .yml / .js / .toml in the repo
    -> docs/acceptance-criteria/.../GE-122a-1.yaml   (the AC that specifies it)
    -> tickets/.../.pending/adr_handoff.json         (a pending handoff)
       nothing else
```

No pre-commit hook invokes it. No CI workflow invokes it. The one registered hook with a
similar name, `check-decision-number-uniqueness`, runs a **different** script
(`check_adr_collision.py`) — and see `KI-CG-022`: that registration itself exists only on
the branch.

**Root cause.** Six review rounds and five fix commits hardened a `main()` that no runner
calls. The commit immediately before the discovery is titled *"the fail-closed contract was
never wired to the exit code"* — and nothing reads that exit code.

The epic's own `Master_Plan.md` named this outcome in advance:

> The trap this epic is most likely to fall into: **a guard that is built, tested green, and
> registered nowhere.**

and its Success Criteria require *"one whole-collection uniqueness pass, **registered in
`commit_guardian.json`** and reachable through its production entry point — not a second
inert detector."* **That criterion is not met.** The epic was commissioned because three
whole-collection detectors were already registered nowhere. It produced a fourth.

**Why nothing caught it.** Every round verified behaviour by importing the module or running
the script directly. Not one asked what invokes it in production. Each round's verification
was accurate and none of them addressed the question. This register's recurring lesson — *a
signal computed correctly and then not consumed* — applied to the entire component, and the
reviews inherited the blind spot from the thing they were reviewing. Generalised as
`KI-TQ-007` in the testing-quality register.

**Fix direction.** **Do not register it in the same change that ships it.** See
`KI-BO-030` — doing so today makes the package uninstallable. Required order: scaffold the
missing namespace roots, **then** register, **then** re-run the deployed-consumer test.

**Pattern:** `docs/reference/false-green-mechanisms.md` — a gate whose reachability was
never asked about; verification that stops at the function and never reaches the entry point.

## Resolution

Verified 2026-09-25 against `origin/main` (`4b05997a`); every claim in the Symptom is gone.

- **Code on main.** `e429421e` (PR #495, 2026-08-26) merged
  `templates/scripts/commit_guardian/check_identifier_uniqueness.py` with
  `_uniqueness_scanners.py` and `_uniqueness_types.py`.
- **Registered in the hook registry.** `243b6489` (PR #635, 2026-09-01, *"register the
  whole-collection numbering pass so it actually runs (GE-122d-6)"*) added
  `"id": "check-identifier-uniqueness"` to `commit_guardian.json` (line 578). Its entry runs
  `run_hook.py .../check_identifier_uniqueness.py`. The same PR added
  `scripts/build_architecture_scaffold.py`, which scaffolds the namespace roots. That follows
  the order this KI's Fix direction required (see `KI-BO-030`).
- **Present in the generated pre-commit config.** `.pre-commit-config.yaml` is gitignored and
  built from the registry. The deployed copy carries `id: check-identifier-uniqueness` with
  `always_run: true, pass_filenames: false`.
- **Runs in CI.** `8cc9fe3c` (PR #682, GE-122d-1) added the `numbering-guarantee-valid` job to
  `.github/workflows/ci.yml`. It runs `pre-commit run check-identifier-uniqueness`.
- **It runs.** The deployed entry
  `python .leafcutter/scripts/commit_guardian/run_hook.py .leafcutter/scripts/commit_guardian/check_identifier_uniqueness.py`
  exits 0 and reports all four namespaces as `OK`. It inspected 4239 acceptance-criteria,
  45 decisions, 27 diagrams and 327 work-items.
- **Tests.** `python -m pytest unit_tests/commit_guardian/test_ge_122d_6.py
  unit_tests/commit_guardian/test_ge_122d_1.py unit_tests/portability/test_ge_122d_6.py -q`
  passed with 7 tests in 48s.

---
