---
title: "KI-CG-031 — `scan_decisions` and `scan_diagrams` fail silently while their sibling scanner logs"
description: "low, but it makes every misconfiguration harder to diagnose than it should be"
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

# KI-CG-031 — `scan_decisions` and `scan_diagrams` fail silently while their sibling scanner logs

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low, but it makes every misconfiguration harder to diagnose than it should be
- **Status:** open — **the code is NOT on `main`**; lives only on unmerged PR #495
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** PR #495's `_uniqueness_scanners.py` (`scan_decisions`, `scan_diagrams`) against
  `_work_items_scanner.py`

**Symptom.** When a namespace root is missing, `_work_items_scanner.py` logs:

```
[check_identifier_uniqueness] WARNING: cannot read <path>/tickets/ticket_lifecycle.json
```

`scan_decisions` and `scan_diagrams` return `passed=False` for an absent root with **no log
line at all**.

**Evidence that this costs real time.** Three failing tests were first read as "the lifecycle
config is missing" because that was the only namespace that said anything; the fixtures were
in fact missing **three** roots, and the two silent ones were only found by printing the
verdict directly. That mis-diagnosis is also recorded from the other side, as the second
instance in `KI-TQ-005`. Since the fail-closed contract now blocks the commit, an operator
hitting this sees a non-zero exit with one namespace named and two staying quiet.

**Fix direction.** Give the silent scanners the same WARNING the work-items scanner already
emits. The `unresolvable_namespaces` field added for `KI-CG-007` already carries the
information; this is only about surfacing it at the point of failure.

---
