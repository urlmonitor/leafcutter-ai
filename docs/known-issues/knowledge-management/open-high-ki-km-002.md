---
title: "KI-KM-002 — 244 of 607 done ACs have no covering test; the ratchet holds the floor, TQ-400d owns the drawdown"
description: "KI-KM-002 — 244 of 607 done ACs have no covering test; the ratchet holds the floor, TQ-400d owns the drawdown"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - knowledge_management
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
---

# KI-KM-002 — 244 of 607 done ACs have no covering test; the ratchet holds the floor, TQ-400d owns the drawdown

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — floor ratcheted by `KM-ADM-005`; retirement owned by `TQ-400d` (draft, unbuilt)
- **Occurrences:** 1
- **First seen:** 2026-08-13 (measured) · **Last seen:** 2026-08-18
- **Where:** the AC store as a whole; ratchet at `unit_tests/docs/test_artifact_graph_covers_scope.py`

**Symptom.** Roughly 40% of ACs marked `work_status: done` carry no `# covers:` test tag
anywhere in `unit_tests/`, `tests/`, or `leafcutter-web/`. "Done" therefore does not mean
"test-proven" for most of the store's history, and any tool that counts done ACs as
covered is reporting a number nobody computed.

**Root cause.** `check-done-proof` is **diff-scoped**: it evaluates only the ACs changed
in the current commit or PR, and never re-examines a done AC that predates the gate. The
gate is genuinely enforced — it just never looked at the back catalogue.

**Evidence.** 607 `work_status: done` ACs; 363 tagged by at least one `# covers:`
reference; 244 untagged (measured 2026-08-13). `HIGH_WATER_MARK = 244` in the ratchet
test fails the build if that count rises.

**What is and is not fixed.** `KM-ADM-005` shipped the measurement, the scope disclosure
on the `test-covers` edge, and the ratchet — so the backlog cannot grow. It does **not**
retire any of the 244.

**Who owns the retirement (corrected 2026-08-18).** This entry previously said the
drawdown "has no AC and no owner". That was wrong on the day it was written.
`TQ-400d` — "the pile of unproven finished work gets worked through, not written off",
authored 2026-08-17 with five L2 children covering the worked list, per-item decisions,
progress measurement and a triage how-to — owns exactly this pile. `TQ-400a` owns the
store-wide sweep that produces the inventory. Do **not** author a new AC for it; the
work is specified and unbuilt, which is a scheduling problem, not a gap.

**Watch out — the pile has two different counts.** `KM-ADM-005` says 244 of 607
(2026-08-13, all levels, ids quote-stripped before joining); `TQ-400`'s L0 notes say 240
of 641 (2026-08-17, done L2/L3 records only). Neither cites the other, so the delta
cannot be read as progress. Reconcile the inclusion rules before triaging, and state the
rule alongside whichever number you publish.

**Related.** `ACS-1100-honest-coverage-answers` (draft, unbuilt, `scope: standing`) is the
general contract this is one instance of, and the disagreement above is that contract's
defect occurring inside its own reconciliation. The two are cross-linked in the store as
of 2026-08-18: `ACS-1100` notes carry a per-L1 breakdown of what `KM-ADM-005` already
satisfies, and `KM-ADM-005` carries `doc_links` back to `ACS-1100` and `TQ-400d`.

---
