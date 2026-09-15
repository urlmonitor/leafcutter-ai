---
title: "KI-CG-20260901-authoring-hook-scans-the-whole-collection-on-every-edit — every Edit/Write pays a full four-namespace numbering scan, whatever file was touched"
description: "KI-CG-20260901-authoring-hook-scans-the-whole-collection-on-every-edit — every Edit/Write pays a full four-namespace numbering scan, whatever file was touched"
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

# KI-CG-20260901-authoring-hook-scans-the-whole-collection-on-every-edit — every Edit/Write pays a full four-namespace numbering scan, whatever file was touched

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** low
- **Status:** open — no AC. Deliberately not fixed in the change that introduced it.
- **Occurrences:** 1 (2026-09-01, filed at introduction rather than after it bit someone)
- **First seen:** 2026-09-01 · **Last seen:** 2026-09-01
- **Where:** `templates/hooks/check_identifier_uniqueness_authoring.py` → `main()`

**What it does.** The hook is a `PostToolUse` handler on Edit|Write. It takes no account of
which file was edited: every invocation runs `evaluate_identifier_uniqueness` over the whole
collection — acceptance-criteria, decisions, diagrams and work-items. Editing a README costs
the same full scan as editing an AC record.

**Measured, not estimated.** 1.36 s per invocation against this repository, versus a
configured timeout of 20 s. Two independent reviews measured it, the earlier one at ~0.5 s;
the spread is itself informative, since the cost tracks collection size and the store grows
monotonically. For scale, the pass currently inspects roughly 3750 acceptance-criteria
records, 38 decisions, 25 diagrams and 298 work-items on each keystroke-level edit.

**Why it is low and not medium.** Nothing is wrong. It does not block, it does not report
falsely, and it is an order of magnitude inside its timeout. This is a design-breadth
question, not a defect, and it is filed at introduction so the decision is visible rather
than discovered later by someone bisecting a slow session.

**What makes it worth recording anyway.** Every other authoring-time hook in the same
directory scopes itself before doing real work — `check_exception_handling_hook.py` filters
to `.py` early, `ticket_frontmatter_guard.py` resolves and filters to the specific edited
ticket path. This one is the outlier, and the deviation is undocumented, so the next reader
cannot tell whether the breadth is deliberate (mirroring the commit-time hook's own
`always_run: true` whole-collection semantics, which would be a coherent reason) or simply
an oversight. Either answer is fine; not knowing which is the problem.

**A second, smaller thing in the same function.** `sys.stdin.read()` is called and its result
discarded — the payload is never parsed, and the hook locates the project from `Path.cwd()`
instead. Anyone extending this hook to be file-scoped will reach for the payload's
`file_path` and find the read already there, looking as though it is being consumed.

**Fix direction, in the order that preserves the most optionality:**

1. **Decide and record the intent** before changing behaviour. If whole-collection breadth is
   deliberate, say so in the module docstring and this entry closes as won't-fix. That is a
   one-line change and it is the highest-value action here.
2. **If it is not deliberate:** scope the scan by the edited path from the payload, matching
   the sibling hooks. This only becomes worth the risk when the cost is felt — a scoped
   authoring check that disagrees with the unscoped commit check would reintroduce
   `GE-122d-1`'s stage-disagreement defect, which is a far worse failure than 1.36 s.
3. **Re-measure before acting either way.** The number will have moved; the store grows.

**Related.** `GE-122d-1` (the criterion this hook implements — one rule, three stages, one
answer; any scoping change must not break that agreement). `KI-CG-012`, `KI-CG-019`
(sibling hooks whose defects are the opposite shape: doing too little rather than too much).

**Pattern:** a hook that is correct and cheap today, whose cost is a function of a
monotonically growing store, with no recorded decision about whether the breadth was chosen.

---
