---
title: "KI-ACS-015 — A `test_spec` descriptor has no link to the criterion it was promised for, so \"which behaviour is this proof for\" is unrepresentable"
description: "KI-ACS-015 — A `test_spec` descriptor has no link to the criterion it was promised for, so \"which behaviour is this proof for\" is unrepresentable"
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

# KI-ACS-015 — A `test_spec` descriptor has no link to the criterion it was promised for, so "which behaviour is this proof for" is unrepresentable

> One known issue, split out of `docs/known-issues/ac-store.md` on
> 2026-09-14. Index: [ac-store.md](../ac-store.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `config/ac_store_schema.json` → `properties.test_spec[]`

**Symptom.** A `test_spec` entry carries `name`, `target_dir`, `framework`, `type`, `angle` and
`description`. It carries **nothing identifying which Then clause it was written to prove.** An
AC with four criteria clauses and four descriptors records no mapping between them; the pairing
exists only in the author's head and, loosely, in the prose of `description`.

**Where it bites.** `BP-1100g-4` requires a refusal naming *"the piece of work, the stated
behaviour, and the kind of proof that was promised and never claimed."* Two of those three are
directly available — the AC id, and the `angle`. The third is not derivable from the store at
all, so the AC as written cannot be satisfied exactly. That ticket resolves it by approximation
(name the AC leaf and its `criteria`, plus the descriptor's `description`), which is adequate for
L2/L3 leaves where one leaf is roughly one behaviour, and explicitly forbids the implementer from
adding a `criterion_ref` field as an unscoped schema change.

**Why medium and not low.** It is fine today because leaves are small. It stops being fine in two
directions that are already in motion: an L2 with several distinct Then clauses cannot say which
descriptor covers which, and any future check comparing promises against claims per-behaviour —
which is precisely the direction `BP-1100g` is heading — has to operate per-AC instead, coarsening
its own signal. The approximation is also invisible: nothing marks the resulting refusal message
as approximate, so it reads as precise.

**Fix direction.** An optional `criterion_ref` on the descriptor, identifying the clause by index
or by a short authored slug. Optional matters — 3,000+ existing descriptors have no such link and
a required field would fail the store wholesale. Then have `it-po` populate it going forward, and
let any per-behaviour consumer degrade explicitly to per-AC when it is absent, rather than
silently.

Do **not** infer the mapping by matching descriptor `description` text against clause text. That
is the same "read the prose and guess" move this component family exists to eliminate, and it
would be a guess presented as a citation.

**Related.** `KI-ACS-013` (`delivers_to`/`expects_from` keyed on different things — the same
class: an edge the store implies but does not represent). `KI-ACS-012` (leaves with no
`test_spec` at all).

**Pattern:** a record that carries the *what* of a promise but not the *what for*, where the
missing half is only noticed by the first consumer that needs to cite it.

---
