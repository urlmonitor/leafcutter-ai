---
title: "Reference: AC IDs, Hierarchy, and covered_by Scope"
description: "Lookup reference for the AC identifier format and full regex, the id-derived parent algorithm, and the direct-children scope rule that governs every covered_by list in the AC store."
type: reference
status: active
created: 2026-09-22
last_updated: 2026-09-22
components:
  - ac_store
  - build_pipeline
related_docs:
  - docs/reference/ac-schema.md
  - docs/how-to/ac-traceability-store.md
  - docs/acceptance-criteria/README.md
---

# AC IDs, Hierarchy, and covered_by Scope

> **Parent document:** [ac-schema.md](ac-schema.md)

Reference for the acceptance-criterion identifier format, the algorithm that derives
a parent AC ID from a child ID, and the direct-children scope convention that governs
every `covered_by` list in the store.

---

## ID Format and Assignment

AC IDs follow the pattern `PREFIX-NNN`, where `NNN` may be followed by
optional hierarchical suffix segments. Compound prefixes (two uppercase
groups joined by a hyphen, e.g. `KM-DBF`) are also accepted.

| Part | Rules |
|---|---|
| `PREFIX` | 2–6 uppercase ASCII letters. Derived from the component's `prefix` field in `docs/acceptance-criteria/index.yaml`. May itself contain a hyphen-separated uppercase sub-group for compound namespaces (e.g. `KM-DBF`, `KM-KQS`). |
| `-` | Literal hyphen separator. |
| `NNN` | One or more digits (historically three zero-padded digits, e.g. `001`; the schema accepts any positive integer). |
| Hierarchical suffix | Optional. See the Hierarchical AC IDs table below. |

**Examples:** `FIN-001`, `AUTH-007`, `BP-042`, `ACS-100`, `KM-DBF-001`.

**Assignment:** IDs are assigned at creation time and never reused. If an
AC is deprecated, its ID remains reserved so that historical references
(e.g. in commit messages or tickets) remain resolvable.

**Full ID regex:** `^[A-Z]{2,6}(-[A-Z]{2,6})?-\d+([a-z]\d*(-\d+[a-z\d]*(-[a-z\d]+)?)?|-\d+[a-z\d]*(-[a-z\d]+)?)?$`

This single regex covers all supported forms:

| Form | Example | Matches |
|---|---|---|
| Root / base | `ACS-100`, `FIN-001` | `PREFIX-\d+` |
| Compound-prefix root | `KM-DBF-001` | `PREFIX-SUB-\d+` |
| L1 alpha | `ACS-100a`, `ACS-200d` | `PREFIX-\d+[a-z]` |
| L1 alpha with digit suffix | `BP-800a2` | `PREFIX-\d+[a-z]\d+` |
| L2 alpha-first | `ACS-500a-1` | `PREFIX-\d+[a-z]-\d+` |
| L2 numeric-only (no alpha L1) | `BO-510-1`, `BO-610-3` | `PREFIX-\d+-\d+` |
| L2 with trailing alpha | `ACS-300g-4a`, `PER-100d-2a` | `PREFIX-\d+[a-z]-\d+[a-z]` |
| L3 alpha extension (alpha-first) | `ACS-500a-1-i`, `ACS-1100b-3-i` | `PREFIX-\d+[a-z]-\d+-[a-z]+` |
| L3 alpha extension (numeric-only) | `BO-510-3-i`, `BO-610-4-i` | `PREFIX-\d+-\d+-[a-z]+` |
| L3 numeric extension | `BO-300a-2-1`, `BP-900a-1-1` | `PREFIX-\d+[a-z]-\d+-\d+` |

### Hierarchical AC IDs and Parent Derivation

ACs form a hierarchy. Child ACs extend the root pattern with additional
segments. The parent ID is derived from the child ID by stripping the last
segment. This derivation is implemented in `scripts/ac_store/ac_parent_id.py`
and is the canonical algorithm for all parent-child enforcement (pre-commit
hooks, store-wide scans, agent auto-updates).

| Level | Format | Example | Parent |
|---|---|---|---|
| L0 (root) | `PREFIX-NNN` | `ACS-100` | (none) |
| L1 (alpha) | `PREFIX-NNNx` | `ACS-100a` | `ACS-100` |
| L2 (numeric) | `PREFIX-NNNx-N` | `ACS-100a-1` | `ACS-100a` |
| L3 (extension) | `PREFIX-NNNx-N-y` | `ACS-100a-1-i` | `ACS-100a-1` |

**Derivation rules (ACS-100i-1):**

1. If the ID matches `^[A-Z]{2,6}-[0-9]{3}$` (root pattern): no parent (`None`).
2. If the ID matches `^[A-Z]{2,6}-[0-9]{3}[a-z]+$` (alpha suffix directly on the
   numeric part, no hyphen): strip the trailing lowercase letters.
   Example: `ACS-100a` → `ACS-100`.
3. Otherwise: strip the last hyphen-delimited segment (everything after the final `-`).
   Examples: `ACS-300h-1` → `ACS-300h`; `ACS-300h-2-i` → `ACS-300h-2`.

Use `derive_parent_id(ac_id)` from `scripts/ac_store/ac_parent_id.py` rather than
re-implementing this logic inline.

---

## covered_by — Scope Convention

**`covered_by` is a DIRECT-CHILDREN list, not a subtree list.**

A parent AC lists its immediate children only. It does **not** list
grandchildren or any deeper descendant. A descendant is reached by following
the chain one link at a time: `L0.covered_by → L1.covered_by → L2.covered_by → L3`.

```yaml
# CORRECT — ACS-100 lists only its L1s
id: ACS-100        # L0
covered_by:
  - ACS-100a       # L1 (direct child)
  - ACS-100b       # L1 (direct child)

id: ACS-100a       # L1
covered_by:
  - ACS-100a-1     # L2 (direct child)

# WRONG — ACS-100a-1 is a grandchild of ACS-100 and must NOT appear here
id: ACS-100
covered_by:
  - ACS-100a
  - ACS-100a-1     # <-- remove; ACS-100a already carries this link
```

Alongside child AC IDs, a **leaf** AC's `covered_by` may hold test file paths
(`unit_tests/test_x.py`, optionally `::test_function`). Mixing the two on one
record is legal and occurs in the store today; only AC-ID entries are subject
to the direct-children rule.

### Why direct children — derived from tool behaviour, not preference

This convention is not a style choice. Every tool that reads `covered_by`
already assumes single-link semantics; a subtree list breaks or degrades each
of them:

| Tool | Behaviour | What it implies |
|---|---|---|
| `check_ac_parent_covered_by.py` (pre-commit, blocking) | For a staged child, computes `derive_parent_id(child_id)` and requires the child to appear in **that one record's** `covered_by`. It never inspects a grandparent. Its ACS-100i-3 decision entry states it explicitly: *"grandparent ACs are not required to list grandchildren directly"*, with six `TestThreeLevelAncestryChain` tests pinning that behaviour. | A grandchild entry satisfies nothing. It is dead weight the hook cannot read. |
| `scan_ac_orphans.py` (store-wide scan) | `find_orphaned_children()` does the same single-hop check for **every** record on disk, at every level including L2→L3. | Same conclusion, applied store-wide: only the immediate parent's list can clear an orphan. |
| `done_proof.py` `_resolve_all_child_ids()` | Flattens a composite to its leaves by **recursing** into each entry's own `covered_by`. The recursion is only well-formed if each level lists direct children; a subtree list makes the same descendant reachable by two paths (survivable only because of the `_seen` cycle guard). | The traversal is designed around direct-children lists. |
| `approve_acs.py` | Iterates a goal AC's `covered_by` and treats **every entry as a leaf** to promote `reviewed → approved`. | A subtree list would sweep intermediate nodes into a leaf-only promotion. |
| `check_ac_limits.py` | Counts children via `_derive_parent_id` ID-string derivation, deliberately **not** via `covered_by` (GE-106, so cross-links cannot game the caps). | `covered_by` carries no cap weight either way — so a subtree list buys nothing and only adds ambiguity. |

The decisive asymmetry: under direct-children semantics every entry is
load-bearing and machine-checkable. Under subtree semantics a grandchild entry
is unverifiable — no tool requires it, no tool reads it, and no tool would
notice if it went stale or named a record that no longer exists.

### Consequences

1. **Do not add a descendant to an ancestor's `covered_by`.** If you find one,
   remove it — but first confirm the descendant's own immediate parent lists
   it, so the link is preserved rather than lost.
2. **Do not "repair" a missing grandchild link by promoting it upward.** The
   repair is to add it to its immediate parent, which is the only record any
   tool consults.
3. **A record whose ID does not follow the canonical scheme above cannot be
   linked structurally at all.** `derive_parent_id` is purely lexical, so a
   child whose declared `depends_on` parent is not its ID-derived parent is
   invisible to both the hook and the scan, in both directions. Prefer
   canonical child IDs (`ACS-100a-1`, not a numeric sibling like `ACS-101`
   standing in as a child of `ACS-100`) so the link the store records is the
   link the tooling can see.

---

## See Also

- [ac-schema.md](ac-schema.md) — parent document; the field-by-field AC YAML schema.
- [ac-schema.md § Pre-Commit Hooks](ac-schema.md#pre-commit-hooks) — the hooks that enforce the ID format and the parent-child links described here.
- [ac-schema.md § Agent Integration Points](ac-schema.md#agent-integration-points) — the authoring-agent protocol that writes the parent `covered_by` link.
- `scripts/ac_store/ac_parent_id.py` — the canonical `derive_parent_id()` implementation.
