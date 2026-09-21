---
title: "KI-BP-004 — A worktree's deployed hooks are frozen at build time, so after merging `main` the gates enforce the previous ruleset"
description: "KI-BP-004 — A worktree's deployed hooks are frozen at build time, so after merging `main` the gates enforce the previous ruleset"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - build_pipeline
related_docs:
  - docs/known-issues/build-pipeline.md
  - docs/known-issues/README.md
---

# KI-BP-004 — A worktree's deployed hooks are frozen at build time, so after merging `main` the gates enforce the previous ruleset

> One known issue, split out of `docs/known-issues/build-pipeline.md` on
> 2026-09-14. Index: [build-pipeline.md](../build-pipeline.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-25
- **Where:** `scripts/build.py` deploy step / `<worktree>/.leafcutter/scripts/commit_guardian/`; no staleness check anywhere in the commit path

**Second occurrence, 2026-08-25 — the false-block direction, observed end to end.**
Committing a merge of `origin/main` into a review branch, `check-contract-shrinking` blocked
with a list of deleted test functions. Every one of them was deleted **by main**, arriving
through the merge; the branch had deleted nothing. Main already carries the fix for exactly
this — the merge-scoping logic in `_merge_scoped_paths()`, whose changelog entry
(`2026-08-18-1920-merge-commits-no-longer-trip-the-contract-shrinking-guard-on-the-base-branch-s-history.md`)
was *inside the very merge being committed*. The worktree's deployed hook predated it.

Rebuilding the worktree's deploy (`python scripts/build.py --target-dir <worktree>`) made
`_merge_scoped_paths` present and the same commit passed on its own merits. Worth recording
because the tempting response is `SKIP=check-contract-shrinking`, which would have worked,
produced the same green, and told the author nothing — the fix was already written and
merely undeployed. A staleness check would have named that in one line.

**Symptom.** `build.py` copies hook code into `.leafcutter/`. Nothing re-runs it and nothing
compares it against the source tree, so the deployed copy is a snapshot of whenever the
worktree was built. Merge `origin/main` into a long-lived branch and the *source* advances
while the *running gates* do not: every commit afterwards is judged by the older ruleset.
Both directions are wrong. A rule fixed on `main` still fails here; a rule *added* on `main`
does not run at all, and its absence is indistinguishable from a pass.

**Evidence.** A worktree built on 2026-08-17 19:38, then merged with `origin/main` on
2026-08-18. `check-doc-frontmatter` failed on seven generated agent cards with
`unknown doc type: card; valid values: adr, architecture, explanation, how-to, reference,
retro, tutorial` — a seven-value list. But `config/doc_types.json` at that same commit
contains **ten** entries including `card`, and the file the hook is supposed to read was
right there in the worktree.

The deployed hook was simply old:

```text
$ grep -c "_find_doc_types_json" <worktree>/.leafcutter/scripts/commit_guardian/doc_type_validators.py
0
$ python <worktree>/scripts/build.py --target-dir <worktree> --force-breaking
$ grep -c "_find_doc_types_json" <worktree>/.leafcutter/scripts/commit_guardian/doc_type_validators.py
4
$ HOOK_ROOT=<worktree> python <worktree>/.leafcutter/scripts/commit_guardian/check_doc_frontmatter.py \
    docs/agents/cards/python-coder.card.md
✅ PASSED: 1 doc(s) passed frontmatter validation
```

The deployed copy predated GE-118c entirely — it did not contain the resolver function at
all, so it was falling back to the narrow constant that GE-118c had already deleted from the
source. Rebuilding fixed it outright.

**Why this is not KI-BP-003.** BP-003 is a *path-resolution* gap: current code that cannot
find a reachable file. This is a *staleness* gap: code that is not current. They present
almost identically — a hook complaining about something the source says is fine — and the
first was mistaken for the second during this session. The distinguishing check is to diff
the deployed file against its template, not to reason about paths.

**Fix direction.** Make staleness detectable rather than relying on discipline. A cheap
version: have the pre-commit entrypoint compare `.build_manifest.json` against the source
templates' hashes and refuse (or warn loudly) when they diverge. `check_build_drift` already
exists and already reasons about deploy parity — extending it to guard the hooks' own
freshness is the natural home. Until then, treat `build.py --target-dir <worktree>` as a
mandatory step immediately after every `git merge origin/main`, and distrust any hook
verdict — pass or fail — taken from a worktree built before the merge.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M2 (the deployed layout differs
from the source you are reading), in its staleness form rather than its missing-file form.

---
