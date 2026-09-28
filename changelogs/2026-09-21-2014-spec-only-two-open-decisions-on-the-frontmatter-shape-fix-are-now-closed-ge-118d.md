---
title: "Spec only: two open decisions on the frontmatter-shape fix are now closed — priority raised to critical, resolver's home settled (GE-118d)"
date: "2026-09-21"
time: "20:14"
type: manual
components: 
  - commit_guardian
  - knowledge_management
summary: "Closed two open decisions on an already-specified fix for a blocking known issue — no behaviour changed and the defect is still live — so implementation can start without re-litigating either one."
description: "Follow-up to the earlier 2026-09-21 spec-only entry for GE-118d/KM-KGS-100d-3 (commit cbdbfb99), which specified the frontmatter path-shape fix for KI-CG-008 but left two questions open. This commit closes both: priority is raised from medium to critical on all seven affected ACs (GE-118d, GE-118d-1, GE-118d-2, GE-118e, GE-118f, KM-KGS-100d-3, KM-KGS-100d-3-i), and the shared path-resolver's home is settled as a new top-level scripts/frontmatter_path_resolver.py rather than the commit-guardian template tree. No criteria fields touched; AC store only."
commits: 
  - de442295
breaking: false
---

## Entry

### What this is

A follow-up to this morning's spec-only entry for `KI-CG-008` (GE-118d and
KM-KGS-100d-3, commit `cbdbfb99`), which specified the fix but left two decisions open
before implementation could start. This commit closes both. **No code changed** — the
crash in `frontmatter_validators.py` and the silent drop in `knowledge_query.py` are
both still live.

### Decision 1 — priority raised from medium to critical, on all seven ACs

`GE-118d`, `GE-118d-1`, `GE-118d-2`, `GE-118e`, `GE-118f`, `KM-KGS-100d-3`, and
`KM-KGS-100d-3-i` were authored `priority: medium` by store convention, inherited from
the parent record. The evidence does not support that grade: `KI-CG-008` is a
registered blocker, at least 33 of the reporting adopter's 50 documents use the shape
that crashes the guard, and because the hook raises rather than refusing, the field
workaround is `SKIP=check-doc-frontmatter` — a working gate switched off entirely. All
seven are now `priority: critical`.

### Decision 2 — the shared resolver's home is settled

The new routine both consumers will call — `frontmatter_validators.py`'s guard and
`knowledge_query.py`'s edge builder — now has a declared home:
**`scripts/frontmatter_path_resolver.py`**, a new top-level module, not
`templates/scripts/commit_guardian/`.

The deciding fact is tier: the template tree is the *compiled* tier (its `.py` files
have config placeholders injected at build time), while top-level `scripts/` is copied
verbatim. A resolver with no config-dependent behaviour does not belong in the tier
that runs it through config injection. Two supporting reasons: the one existing
precedent for a gate sharing a leaf module runs the opposite dependency direction, and
`GE-118f` already declares the routine as belonging to both `commit_guardian` and
`knowledge_management` rather than either alone. `GE-118f`'s manifest requirement is
narrowed accordingly, naming the exact two deploy-list entries the implementer needs
rather than leaving the choice open.

### Why it matters that this is still spec-only

Nothing behavioral changed and `KI-CG-008` is still an open blocker. What changed is
that two questions the original spec deliberately left for later are now answered, so
an implementer can start without re-litigating either one.
