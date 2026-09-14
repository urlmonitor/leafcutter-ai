---
title: "KI-KM-001 — SourceFile → AC does not exist, so nothing can answer \"which ACs govern this file?\""
description: "KI-KM-001 — SourceFile → AC does not exist, so nothing can answer \"which ACs govern this file?\""
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

# KI-KM-001 — SourceFile → AC does not exist, so nothing can answer "which ACs govern this file?"

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../knowledge-management.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open — recorded as a `status: absent` edge, no AC authored
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/reference/artifact-knowledge-graph.graph.json` (edge `source-implements-ac`)

**Symptom.** The graph has no edge from a source file back to the acceptance criteria
that govern it. Before touching a file you cannot mechanically ask what behaviour is
specified against it, so "what must I not break here?" is answered by reading and
recall rather than by traversal. This is the single most load-bearing missing relation
for refactoring, and it is the direction the graph was commissioned to serve.

**Evidence.** The edge is recorded in the graph JSON with `"status": "absent"` and no
`field`, alongside three other absent edges (`test-exercises-source`,
`changelog-delivers-ac`, `mockup-realizes-ac`). The reverse edge (`ac-implements`, AC →
SourceFile via `implemented_by`) exists but is rated untrusted, so inverting it does not
recover the answer.

**Best available substitute today.** `Ticket.files_touched` → the ticket's
`ac_traceability` block. Two hops, and only as good as the declared file list.

**Why it is not just "not built yet".** The absent edges are drawn in the Atlas as red
dashed gaps precisely so this stays visible. Recording it here escalates it from
"documented gap" to "next design decision" — it needs a decision between marker comments
in source and a derived index built from ticket traceability before any AC can be
written.

**Candidate home when it earns an AC.** `KM-ADM-100b` ("a connection the project does not
have shows up as a gap you can see") — this issue is the highest-value instance of that
L1, and the L1 is where a future child belongs.

---
