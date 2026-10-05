---
title: "KI-CG-20260930-doc-index-transform-prefers-stale-deployed-generator — transform-doc-index imports generate_doc_index from the DEPLOYED directory before the source one, so a stale deployment silently resurrects fixed generator bugs and the transform re-stages the damage into your commit"
description: "high — _find_generator_module searches <output_root>/scripts/ first and repo_root/scripts/ second. When .leafcutter/ predates a generator fix, the hook runs the old code, rewrites docs/INDEX.md wrongly, and git-adds it without being asked. Observed reintroducing the docs/docs/ 404 bug that had been fixed in source five days earlier, putting 192 broken links into a commit that touched no documentation."
type: reference
category: reference
status: active
created: '2026-09-30'
last_updated: '2026-09-30'
components:
  - commit_guardian
  - documentation_system
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260928-mermaid-parent-link-dead-in-deployed-layout.md
---

# KI-CG-20260930-doc-index-transform-prefers-stale-deployed-generator — a fixed bug came back because the hook prefers the deployed copy

- **Severity:** high. A transform-tier hook silently rewrites and **re-stages** a tracked file
  using code that may be arbitrarily old. The author never asked for the change and, because the
  hook `git add`s it, will ship it unless they notice an unexplained deletion count.
- **Status:** open — no AC.
- **Occurrences:** 1 (2026-09-30, committing three known-issue entries; noticed only because the
  commit reported 193 deletions for a change that only added lines).
- **First seen:** 2026-09-30 · **Last seen:** 2026-09-30
- **Where:** `templates/scripts/commit_guardian/transform_doc_index.py`, `_find_generator_module`
  — the candidate search order. The generator itself is `scripts/generate_doc_index.py`.

## Mechanism

`_find_generator_module` searches an ordered candidate list and takes the **first** hit:

1. `Path(__file__).resolve().parents[1]` — the **deployed** layout, `<output_root>/scripts/`
2. `repo_root / "scripts"` — the **source** layout

Candidate 1 wins whenever a deployed copy exists, which in this workspace is always: `.leafcutter/`
is a long-lived install tree shared across worktrees and is only refreshed when someone runs
`build.py`. So a fix landed in `scripts/generate_doc_index.py` has **no effect on the hook** until
the next build — and the hook gives no indication which copy it imported.

The ordering is not obviously wrong on its own: for a consumer install, the deployed copy *is* the
right one, and the docstring says so. The defect is that there is no freshness comparison and no
disclosure, so "deployed" silently means "possibly older than the fix you just made".

## Evidence

Measured on `origin/main` `89613071`, in the worktree whose `.leafcutter` is the shared install
tree:

| copy of `generate_doc_index.py` | occurrences of `map_dir` |
|---|---|
| `scripts/generate_doc_index.py` (source) | **15** |
| `.leafcutter/scripts/generate_doc_index.py` (deployed, imported first) | **0** |

`map_dir` is the parameter introduced by the 2026-09-25 fix, whose own DECISION HISTORY line
reads: *"link targets are relative to the map's folder (`_link`, `map_dir`); link text keeps the
project-root path. **Fixes docs/docs/ 404s.**"* The deployed copy predates it entirely.

**Consequence, observed:** committing three files under `docs/known-issues/` triggered the
transform (its condition is "at least one staged file under `docs/`"). It regenerated
`docs/INDEX.md` with the pre-fix generator and re-staged it. The commit reported
**192 insertions, 192 deletions** on a file the author never touched, rewriting every link from

```
[docs/architecture/components/ac-driven-dev.md](architecture/components/ac-driven-dev.md)
```

to a target prefixed with `docs/`. `INDEX.md` lives *in* `docs/`, so each rewritten target
resolves to `docs/docs/architecture/...`. Verified: `docs/docs/` does not exist;
`docs/architecture/components/` does. All 192 links were broken, and the fix from five days
earlier was undone in the working tree.

## Why this is easy to ship without noticing

The hook is `tier: transform` and exits 0 always (fail-open by contract). It prints a
"Regenerated and restaged" line among dozens of other hook lines. Nothing fails, nothing is
refused, and the file is already staged by the time control returns — so the only signal is a
diff stat the author has to be suspicious of. In this instance the change was caught solely
because the commit's deletion count contradicted an addition-only edit.

## Fix direction

1. **Compare the two candidates rather than taking the first.** If both exist and differ, that is
   a could-not-decide state, not a silent preference: report it and skip, per `check_outcome`'s
   could-not-check vocabulary (`GE-120a-1`). A transform that cannot establish which generator is
   current must not rewrite a tracked file.
2. **Say which copy was used.** The "Regenerated and restaged" line should name the imported
   module's resolved path. One line, and the entire class of "which code actually ran" ambiguity
   disappears.
3. **Prefer source over deployed when a repo root is available** — inverting the candidate order
   for the in-repo case, while keeping the deployed copy first for genuine consumer installs
   where no source tree exists. `_resolve_repo_root()` already distinguishes them.
4. **Separately: a transform should arguably not `git add` a file outside the staged set at all.**
   Regenerating `INDEX.md` when the author staged only `docs/known-issues/*` widens the commit
   beyond what was authored. That is a policy question for whoever owns the transform tier, not
   part of this fix.

## Related

`KI-CG-20260928-mermaid-parent-link-dead-in-deployed-layout` — the mirror image: a hook resolving
paths *into* the deploy directory when it wanted the repo. Both are cases of the deployed/source
boundary being crossed silently rather than deliberately (ADR-001).

**Pattern:** a module resolved by search order rather than by freshness — so a fix in source is
shadowed by an older deployed copy, and the hook that consumes it reintroduces the repaired bug
while reporting success.
