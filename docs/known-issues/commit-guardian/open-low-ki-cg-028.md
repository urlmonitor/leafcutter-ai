---
title: "KI-CG-028 — The diagrams root is hardcoded while its sibling architecture roots are configurable"
description: "KI-CG-028 — The diagrams root is hardcoded while its sibling architecture roots are configurable"
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

# KI-CG-028 — The diagrams root is hardcoded while its sibling architecture roots are configurable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium
- **Status:** open — **the consuming code is NOT on `main`** (PR #495's
  `check_identifier_uniqueness.py`), but the **cause** is on `main` and verified: there is no
  `architecture_diagrams` key in `config/paths.json`
- **Occurrences:** 1
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-26 (re-verified against `37655862`)
- **Where:** `config/paths.json:48-51`; PR #495's `check_identifier_uniqueness.py`

**Symptom.** `config/paths.json` declares the other architecture roots and not this one:

```json
"architecture":            "docs/architecture/",
"architecture_adrs":       "docs/architecture/adrs/",
"architecture_components": "docs/architecture/components/",
```

There is **no `architecture_diagrams` key** — confirmed by direct read at lines 48-51, where
`architecture_components_optional: true` follows and the enumeration ends. The gate hardcodes
`docs/architecture/diagrams/` instead. So of the four namespaces it polices, one has a root a
consumer cannot relocate while its two immediate siblings can.

**Why it matters.** Once the gate is registered (`KI-CG-021`), a consumer that keeps diagrams
anywhere else gets a permanently unresolvable namespace, which under the `KI-CG-007`
fail-closed contract blocks every commit with no configuration escape.

**Fix direction.** Add `architecture_diagrams` to `paths.json` and read the root from it,
mirroring how `architecture_adrs` is already consumed — **non-optional**, since the gate hard-
requires the root to exist. Fold this into the scaffolding work (`KI-BO-030`): the same change
decides where the directory lives and how the gate finds it, and splitting them invites the two
answers to diverge. `docs/reference/architecture-docs-layout.md` is the design note for this.

**Context for whoever picks this up.** `docs/architecture/diagrams/` currently holds 24 files:
13 match the `c{level}-{seq}` pattern the gate's numbering namespace polices, and 11 do not.
Those 11 are a **binding, permanent exemption** recorded in `GE-122e.yaml` / `GE-122b.yaml` by
a PO gate decision of 2026-08-17 — do not renumber them.

---
