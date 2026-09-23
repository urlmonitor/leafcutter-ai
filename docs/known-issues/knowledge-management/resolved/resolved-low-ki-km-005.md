---
title: "KI-KM-005 — Six reviewed `KM-ADM-*` ACs sit as orphan L2s with no L0/L1 parent"
description: "KI-KM-005 — Six reviewed `KM-ADM-*` ACs sit as orphan L2s with no L0/L1 parent"
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

# KI-KM-005 — Six reviewed `KM-ADM-*` ACs sit as orphan L2s with no L0/L1 parent

> One known issue, split out of `docs/known-issues/knowledge-management.md` on
> 2026-09-14. Index: [knowledge-management.md](../../knowledge-management.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** resolved on branch `coverage-answers-reconcile`, pending user approval of the
  framing — parent authored as `KM-ADM-100` with L1s `KM-ADM-100a`–`d`. Delete this section
  when that lands on main.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `docs/acceptance-criteria/knowledge-management/KM-ADM-00{1..6}.yaml`

**Symptom.** All six ACs governing the artifact knowledge graph are `level: L2`,
`readiness: reviewed`, and parentless — they sit loose at the top of the component
directory rather than under an L0/L1 benefit statement. They were authored one at a time
by `/quick-fix`, which produces a single L2 per run and does not graft it onto a tree.

**Consequence.** They express no shared benefit, so the body of work they constitute is
not visible as one thing to anyone reading the store top-down. Whether any traversal or
prioritiser actually skips them is **not yet verified** — do not assume it does, and do
not assume it does not.

**Resolution (2026-08-18, product-owner).** `KM-ADM-100` ("rely on the map of how your
project fits together, because it admits what it cannot prove") now parents all six
through four L1s: `100a` trust ratings reflect what runs and state their scope
(`001`, `005`); `100b` a missing connection is visible as a gap (`002`, `003`);
`100c` the links that tell you what a change breaks are followable (`004`); `100d` every
copy of the map agrees (`006`). The six stay in `knowledge-management` — they are one
artifact-map body, and their relationship to `ACS-1100` is inheritance of a standing
contract, not ownership.

**Residual, and the reason this is only half-fixed.** The links are carried by the
`parent` field, `depends_on`, and `covered_by` — **not** by ID derivation. Compound-prefix
ids (`KM-ADM-005`, and `KM-ADM-100a` itself) both derive to `KM-ADM`, which is not an AC,
so `check-ac-parent-covered-by` never fires on them and `check-ac-tree-limits` counts the
new L0 as childless. The back-links are a convention nothing mechanically defends. The
same is already true of the shipped `KM-KGS-100` tree, so this is a store-wide gap in
`derive_parent_id()` for compound prefixes, not a KM-ADM authoring error. Re-IDing is not
an option — ids never change, and `KM-ADM-005` is cited by `# covers:` tags in shipped
tests.

**Related.** This is the structural half of the same problem as KI-KM-002: a shipped
`/quick-fix` AC has no home in the tree that governs its subject.

---
