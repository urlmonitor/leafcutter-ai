---
title: "KI-BO-012 — The fast lane emits no telemetry, so the lane-comparison report can never contain fast-lane data"
description: "KI-BO-012 — The fast lane emits no telemetry, so the lane-comparison report can never contain fast-lane data"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_orchestration
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
---

# KI-BO-012 — The fast lane emits no telemetry, so the lane-comparison report can never contain fast-lane data

> One known issue, split out of `docs/known-issues/build-orchestration.md` on
> 2026-09-14. Index: [build-orchestration.md](../build-orchestration.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — no AC; the BO-2400d family needs the same reconciliation the
  BO-2500d family just had, and that is a product decision
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `templates/workflows-js/fast-lane-ship.js` (the absence), against
  `scripts/agent-health/agent_telemetry.py` and `generate_health_report.py`

**Symptom.** `BO-2400d` promises "See what each build costs and how long it takes". The
telemetry module, its record schema, its failsafe and the lane-comparison report are all
built, tested and `done`. The lane that actually runs never calls any of it.

**Evidence.** `grep -c telemetry templates/workflows-js/fast-lane-ship.js` returns `0`.
The only fast-lane emission of `agent_telemetry.py emit_agent_telemetry` is in
`templates/workflows-js/fast-lane-build.js` — the orphan nothing invokes — at lines 128,
197 and 301. `build_lane_comparison_report` groups records by a `lane` field and its own
docstring states that "a lane with no records is absent from the result", so with zero
fast-lane records the fast lane is absent from every comparison the report can produce.
`BO-2400d-3` ("A report compares fast-lane vs heavy-pipeline cost and time per unit of
work") is `done` and cannot be satisfied today.

**The sharp part.** `BO-2400d-1-i` — "An unreachable telemetry sink is surfaced loudly,
never silently" — is also `done`, and it guards the wrong failure. It detects a sink that
cannot be *written*. It cannot detect a sink nobody *calls*, which is the failure actually
present. A guard aimed one step downstream of the real gap reads as coverage.

**Why it recurred.** KI-BO-006 warned that deleting the orphan would silently retire
prompt caching. That was right about the category and counted only one instance. The
caching half was fixed (BO-2400c-1-iii) and the entry then read as discharged, while the
orphan had been sheltering a second capability the whole time. Found only by auditing the
orphan's full contents while sizing `BO-2400c-1-v` — not by re-reading the KI.

**Fix direction.** Decide first, build second — same order as the BO-2500d
reconciliation. Either wire emission into `fast-lane-ship.js` and re-point `BO-2400d-1`'s
proof at an executed dispatch, or state plainly that the fast lane is untelemetered and
amend `BO-2400d-3` to say what it actually compares. Do NOT delete the orphan until this
is settled — see the second blocker recorded in `BO-2400c-1-v`'s notes. The same audit is
owed to every other capability the orphan references: two have now been found this way and
nobody has enumerated the rest.

---
