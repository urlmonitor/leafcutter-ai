---
title: "KI-CG-20260914-doc-length-blocks-registers — the doc-length refusal makes every known-issues register uncommittable"
description: "high — it blocks the repository's own defect-recording surface, so the cost is"
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

# KI-CG-20260914-doc-length-blocks-registers — the doc-length refusal makes every known-issues register uncommittable

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high — it blocks the repository's own defect-recording surface, so the cost is
  paid in findings that never get written down
- **Status:** open, and live on `main` as of `2026-09-14`
- **Occurrences:** 1 (hit immediately, on the commit filing the two entries above)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/check_doc_length.py`; `check-doc-length` in
  `hooks_manifest.hooks`, `files: ^docs/.*\.md$`; every file in `docs/known-issues/`

**Symptom.** `check-doc-length` was flipped from warn to refuse (PR #801). Its limit is **300
lines**. The known-issues registers are between roughly 1,600 and 4,600 lines, so the gate refuses
any commit touching one:

```
❌  Documentation Length Check — BLOCKED
📄 docs/known-issues/commit-guardian.md   4536 lines (limit: 300) — 4236 lines over
📄 docs/known-issues/testing-quality.md   1656 lines (limit: 300) — 1356 lines over
```

This is not a growth ratchet firing on an increment — it refuses on the absolute size, so *any*
edit to a register is refused, including one that only deletes lines.

**Why this matters more than an ordinary oversized doc.** The registers are where this project
records defects, and the standing instruction for the guardrail owner is to file what is found on
sight. A gate that makes them uncommittable converts every incidental finding into either a
skipped hook or an unrecorded one, and the second is the likely outcome for anyone who does not
know the skip. The entries immediately above this one could only be filed with
`SKIP=check-doc-length`.

**Not caught before landing because CI does not run it.** `.github/workflows/ci.yml` invokes only
the six AC hooks through `pre-commit run`; `check-doc-length` is pre-commit-only. So the flip to
refuse is invisible to every PR check and surfaces solely as a local commit failure.

**The gate's own advice does not fit this surface.** It suggests extracting sections into linked
docs, and names the extraction target from the first heading — here proposing
`how_to_use_this_file.md` at "~4530 lines", i.e. the whole file. A register is an append-only
chronological log of independent entries, not a document with extractable self-contained
sections; splitting it by heading would scatter one searchable history across dozens of files and
break every inbound `KI-` cross-reference.

**Fix direction.** Decide the intended scope before widening enforcement: either exempt
`docs/known-issues/` (a per-path limit or an entry in the gate's exemption registry, matching how
`check-file-size` carries per-kind rules), or give this gate the shrink-only ratchet
`_file_size_ratchet.py` already implements and GE-127f just generalised — so an already-oversized
register can be edited and must not grow, which is the behaviour the flip presumably intended.
Blanket refusal on absolute size against a 300-line limit is not reachable for this surface.

**Pattern:** an enforcement level raised without checking which existing files it makes
unmaintainable — the blast radius landing on the very surface used to record it.
