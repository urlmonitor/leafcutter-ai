---
title: "KI-CG-20260923 — the file-size ratchet has no escape for a file that cannot be split, so an over-limit workflow body can never accept a fix"
description: "check-file-size refuses any growth on an already-over-limit file and offers extraction as the only remedy. A workflow body cannot be extracted from — the E2 engine contextifies it with no module loader — so once such a file is over its limit, every correct change to it is permanently refused."
type: reference
category: reference
status: active
created: 2026-09-23
last_updated: 2026-09-23
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/architecture/adrs/ADR-030-dual-engine-workflow-support.md
---

# KI-CG-20260923 — the file-size ratchet has no escape for a file that cannot be split, so an over-limit workflow body can never accept a fix

> One known issue in the commit-guardian register.
> Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the original
> grading is the `**Severity:**` line below.

- **Severity:** high — it does not corrupt anything, but it makes a whole class of
  source file permanently unmaintainable through the sanctioned path, and the only way
  past it is `SKIP=check-file-size`, which trains people to skip the guard generally.
- **Status:** open — no AC
- **Occurrences:** 1
- **First seen:** 2026-09-23 · **Last seen:** 2026-09-23
- **Where:** `templates/scripts/commit_guardian/check_file_size.py` and
  `_file_size_ratchet.py`; observed on `templates/workflows-js/plan-feature.js`

**Symptom.** A correct, tested, minimal defect fix to `plan-feature.js` was refused:

```
FILE GREW WHILE ALREADY OVER ITS LIMIT:
   templates/workflows-js/plan-feature.js
   Previous length: 2918 lines
   New length: 2921 lines
```

Three content lines, for a fix with an approved AC and a red-then-green behavioural test.

**Why there is no way out for this file.** The ratchet's remedy — the one its own
message and this repo's precedent prescribe — is to extract a cohesive family into a
sibling module, as `build.py` did three times. **A workflow body cannot do that.** Per
ADR-030 the E2 engine contextifies the body with exactly `agent, parallel, pipeline,
phase, log, args, workflow, budget` and **no module loader**, so `plan-feature.js` has
no import mechanism and can never be relieved by extraction. It is also the single
largest workflow in the package and already over limit.

Nor is there a carve-out: `check_file_size.py` and `_file_size_ratchet.py` contain no
`exempt`, `allowlist`, `waiver` or `override` mechanism, and `config/file_size_limits.yaml`
has no workflow-specific entry. So for an over-limit workflow body the ratchet's verdict
is unconditional and permanent.

**A second, quieter half.** The ratchet counts CONTENT lines, which strips comments. A
first attempt to comply cut three multi-line explanatory comment blocks down to trailing
one-liners, taking the raw diff to `13 15` — net **-2** by `git diff --numstat` — and the
hook still reported **+3**, because only the code additions counted. The compaction
therefore bought nothing except worse-documented code. Anyone trying to satisfy this gate
by trimming prose is doing permanent damage for zero benefit, and the hook's output does
not say so.

**Why it matters.** The guard is right in general: unbounded files are real debt, and the
ratchet has already forced several healthy extractions. But a rule whose only remedy is
unavailable for a given file class stops being a ratchet and becomes a freeze. The
observable consequence is the one this register keeps recording in other forms — the
practical response becomes `SKIP=check-file-size`, and a gate that is habitually skipped
protects nothing. This change took the skip, with the reason stated in the commit message.

**Fix direction.** Any of these would close it; the first is the smallest:

- Recognise un-splittable files. A file the build treats as a workflow body (or any file
  declared as such) needs a different rule than "extract something" — e.g. a per-file
  limit that can be re-pinned with an explicit, reviewed justification, the way the
  reachability-exemption registry already works for a different guard.
- Make the refusal message state the CONTENT-line delta and say explicitly that comments
  are not counted, so nobody spends a round trimming prose that cannot help.
- Consider whether a workflow body should be measured at all while ADR-030 gives it no
  means to modularise; if it should, the package needs to offer that means first.

**Pattern:** a guard whose remedy is structurally unavailable to the thing it guards.
Related in spirit to `KI-CG-20260908-file-size-ratchet-refuses-merge-commits` (now
resolved), where the same hook was correct in intent but wrong for one whole shape of
commit.

---
