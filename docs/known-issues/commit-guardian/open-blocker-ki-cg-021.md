---
title: "KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run"
description: "KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run"
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

# KI-CG-021 — The whole-collection uniqueness pass is registered in no hook config and no CI workflow, and has never run

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open — **the code is NOT on `main`**; `check_identifier_uniqueness.py` and its
  four scanners live only on the unmerged PR #495 (`feat/ge-122-integrity-guard`). Filed
  here because it is the gating precondition on landing that branch: the merge must not be
  taken as "the gate now exists".
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

---
