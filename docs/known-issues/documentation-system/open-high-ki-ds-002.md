---
title: "KI-DS-002 — The doc conventions the specialists require are repo documentation, not templates, so none of them is deployed to an adopter"
description: "KI-DS-002 — The doc conventions the specialists require are repo documentation, not templates, so none of them is deployed to an adopter"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - documentation_system
related_docs:
  - docs/known-issues/documentation-system.md
  - docs/known-issues/README.md
---

# KI-DS-002 — The doc conventions the specialists require are repo documentation, not templates, so none of them is deployed to an adopter

> One known issue, split out of `docs/known-issues/documentation-system.md` on
> 2026-09-14. Index: [documentation-system.md](../documentation-system.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-19 · **Last seen:** 2026-08-19
- **Where:** `docs/how-to/documentation/write-reference.md` (exists, not shipped) · no
  corresponding path under `templates/` · no build phase referencing it
- **Reported by:** adopter repo DIAGraph (`roche-sandbox/dia-graph`), against pin `54356a92`

**Symptom.** Every Diataxis specialist opens with a mandatory read of
`docs/how-to/documentation/write-<genre>.md`, named as its single source of truth. KI-DS-001
covers four of those files never having been written. This is the other half, and it applies
to the one that *was*: `write-reference.md` lives in this repo's `docs/` tree, which is
package documentation about the package. It is not a template, so `build.py` never deploys it,
and an adopter's `docs/how-to/documentation/` is empty on a fresh install.

The consequence is that closing KI-DS-001 would fix this repo and change nothing for any
adopter. All five specialists would still be non-functional everywhere the package is
installed, for a different reason, with an identical symptom — the kind of gap that gets
closed twice and reported three times.

**Evidence.** `find templates -name "write-*.md"` returns nothing.
`grep -rn "how-to/documentation\|write-reference" scripts/build_phases.py scripts/build.py`
returns nothing — no phase deploys the path and no phase mentions it. Reported by DIAGraph as
"leafcutter ships no `write-*.md` templates anywhere under `templates/` (searched)", which is
accurate, and independently confirmed here.

**Fix direction.** Ship the conventions as templates —
`templates/docs/how-to/documentation/write-*.md`, deployed **write-if-absent**. That posture
already exists in the build: `build_vision` materialises `docs/vision.md` from
`templates/vision/VISION.template.md` and always passes `force=False`, so a human-curated file
is never clobbered. The conventions want exactly that contract — working defaults on install,
freely editable, never overwritten by a later build.

Weaker alternatives, in descending order: have `/onboard` scaffold them (helps new installs
only, and leaves every existing adopter where they are); or, at minimum, have `package-audit`
report the specialists as non-functional when their convention file is missing, so the gap is
visible before someone dispatches an agent that cannot run.

Note that the fix lands in the **build pipeline** while the defect presents in the
documentation system — the two registers meet here, and a fix filed under only one of them
will look complete from that side.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2, in its never-deployed form: the
package's own tree has the file, so every check run inside the package passes, and no check
runs anywhere else.

---
