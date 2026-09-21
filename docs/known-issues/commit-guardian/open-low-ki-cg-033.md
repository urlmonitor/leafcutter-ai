---
title: "KI-CG-033 — Placeholder marker detection flags markdown emphasis as a list bullet, and its false-positive cost was measured on one marker and claimed for all six"
description: "KI-CG-033 — Placeholder marker detection flags markdown emphasis as a list bullet, and its false-positive cost was measured on one marker and claimed for all six"
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

# KI-CG-033 — Placeholder marker detection flags markdown emphasis as a list bullet, and its false-positive cost was measured on one marker and claimed for all six

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

> **Renumbered 2026-08-26: filed as `KI-CG-017` in PR #575, now `KI-CG-033`.** Same cause as
> `KI-CG-032` above — allocated against a stale snapshot that stopped at `KI-CG-014`. The
> original `KI-CG-017` (`check-build-drift` filtered on the consumer layout path) keeps its
> number: it was there first and is cited from three `GE-126` acceptance criteria
> (`GE-126d-1`, `GE-126e-2-i`, `GE-126e`), all of which mean the `check-build-drift` entry and
> are correct as written. This entry's one inbound citation is repointed in the same commit.

- **Severity:** medium
- **Status:** open — **the code is not on `main`**; it lives on unmerged PR #495, branch
  `feat/ge-122-integrity-guard`. `main` still has only the narrow `\bFIXME\s*:` form and none
  of the widening described below.
- **Occurrences:** 1
- **First seen:** 2026-08-26 · **Last seen:** 2026-08-26
- **Where:** `scripts/build_placeholder_detection.py:114` (`_LEADING_BULLET_REQUIRED`) and
  `:87` (`_LEADING_MARKER_PREFIX`), plus the claims in the comments at `:98` and `:231`

**Two defects. The second is worse than the first.**

**(a) The bullet requirement accepts a bullet *character*, not a list bullet.** The pattern
`r"^\s*(?:[-*+]|\d+[.)])\s*"` matches markdown emphasis and ordered prose:

| Line | Result |
|---|---|
| `*Placeholder* text is shown when empty.` | **flagged** — false positive |
| `**Placeholder** text is shown when empty.` | not flagged — the `\s*` cannot span the second `*` |
| `3. Placeholder naming follows the house style.` | **flagged** — false positive |

Note the italic/bold inconsistency: the same sentence is flagged or not depending on emphasis
style, which is the tell that the rule is matching punctuation rather than structure.

**(b) The recorded claim that these markers carry no false-positive cost is wrong, and wrong in
a specific way worth naming.** The comments state there is "no repo-wide evidence of a
false-positive cost" for `TODO` / `FIXME` / `Replace with`. A repo-wide scan of 5,063 md/yaml
files returns **55 hits**, of which **14** survive purely on the optional-bullet rule
(indentation only, no bullet). Nearly all are plainly false:

```
docs/ticket-lifecycle.md:11,15,19              todo --> in_progress: ...   (Mermaid state transitions)
templates/skills/roadmap-query/SKILL.md:54,58  todo: 1 / todo: 2           (a count field)
templates/skills/signoff/SKILL.md:110,119      Replace with:
ACD-400a-4.yaml:15, BP-900h-4-i.yaml:238,      wrapped prose: "todo -> in_progress -> done"
TKT-500c-6.yaml:16, UXP-411.yaml:28
```

Marker distribution across those 55: **`todo` 42, `<!-- question:` 8, `replace with` 3,
`placeholder` 2.**

**The measurement error, stated plainly, because it is the reusable lesson.** The false-positive
cost was measured for `PLACEHOLDER` only and then asserted for all six markers. `PLACEHOLDER`
accounts for 2 of the 55 hits. So the tightening landed on the marker responsible for 2 and left
untouched the marker responsible for 42. A prior round of the same work made the same shape of
error — a widening measured with a grep that shared the widening's blind spot, reported as "one
instance" when the true cost was 23 false positives across 4,815 files.

**Fix direction.** Require a bullet **followed by whitespace** so emphasis cannot satisfy it, and
decide the ordered-list case deliberately rather than by regex accident. Then re-run the
repo-wide measurement per marker — not in aggregate — before restating any zero-cost claim, and
record the per-marker counts next to the rule so the next person tightening it can see which
marker actually costs anything.

**Pattern:** a claim generalised from the one case that was measured, in a change whose whole
purpose was to bound false positives.

---

> **Entries `KI-CG-021` … `KI-CG-031` are recovered from an unmerged branch.** They were
> written between 2026-08-19 and 2026-08-25 while driving
> `EPIC-GE122UniquenessPassAndRepair`, into a parallel known-issues register that PR #495
> invented with its own id scheme (`KI-CG-9`, `KI-CG-12`, …). That register lost every
> reconciliation conflict against this file and was discarded; a pairwise comparison then
> found the two are disjoint in subject matter, so the analysis below would have been lost
> with the branch. Every entry was re-verified against `main` at `37655862` before being
> filed, and each `Status` line states plainly whether the code it describes is on `main`
> or only on the unmerged branch. Two entries from that set were **dropped** as no longer
> true and are deliberately absent: one about `origin/main`-staleness in
> `test_ge_122e_1.py` (fixed 2026-08-18, the assertion is now a one-directional id-set
> difference) and one about agent cards failing `check-doc-frontmatter` (fixed — `card` is
> now a valid `config/doc_types.json` type and the cards validate clean).

---
