---
title: "KI-CG-20260917-doc-index-hook-staging-loses-unstaged-work — `transform-doc-index` stages its own output mid-commit, so pre-commit cannot restore stashed unstaged changes and the working tree loses them"
description: "KI-CG-20260917-doc-index-hook-staging-loses-unstaged-work — `transform-doc-index` stages its own output mid-commit, so pre-commit cannot restore stashed unstaged changes and the working tree loses them"
type: reference
category: reference
status: active
created: '2026-09-17'
last_updated: '2026-09-17'
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260917-doc-index-hook-staging-loses-unstaged-work — `transform-doc-index` stages its own output mid-commit, so pre-commit cannot restore stashed unstaged changes and the working tree loses them

> Index: [commit-guardian.md](../commit-guardian.md). Filename severity is the three-level
> index bucket (`high`); the original grading is the `**Severity:**` line below.

- **Severity:** high. Uncommitted work vanishes from the working tree during an ordinary
  commit. It can be recovered, but only by someone who knows where pre-commit keeps its
  patches.
- **Status:** open — no AC
- **Occurrences:** 1 (2026-09-16: 8 unrelated unstaged ticket edits lost; restored from a
  backup patch the session had taken)
- **First seen:** 2026-09-16 · **Last seen:** 2026-09-16
- **Where:** `templates/scripts/commit_guardian/transform_doc_index.py:204-208`
  (`subprocess.run(["git", "add", str(index_path)])`), registered as `transform-doc-index`
  (`files: ^docs/.*\.md$`) in `.pre-commit-config.yaml`; interacts with pre-commit's
  `staged_files_only._unstaged_changes_cleared` (pre-commit 4.6.0, installed here)

**Symptom.** A commit touching `docs/**/*.md`, made while `docs/INDEX.md` also had unstaged
changes, left the working tree without **any** of its unstaged changes, including unrelated
files. The loss is not limited to `INDEX.md`.

**Mechanism — read from pre-commit 4.6.0's source; not re-run here, because the git index
in this worktree is shared with other live sessions.**

1. pre-commit diffs the working tree against `git write-tree` (the index *before* hooks run),
   saves the diff as `<store>/patch<ts>-<pid>`, and runs `git checkout -- .`.
2. `transform-doc-index` regenerates `docs/INDEX.md` and **runs `git add` on it**, so the
   index changes under pre-commit.
3. In the `finally`, pre-commit runs `git apply <patch>`. The patch includes the unstaged
   `INDEX.md` hunk, written against the old content, so it fails. `git apply` is
   all-or-nothing, so no file from the patch is applied.
4. pre-commit logs "Stashed changes conflicted with hook auto-fixes... Rolling back fixes...",
   runs `git checkout -- .` again and re-applies the patch. The checkout restores from the
   **index**, which now holds the hook's staged `INDEX.md` rather than the tree the patch was
   taken against. The second `_git_apply` fails the same way and is **not** inside a `try`.
   The error propagates, and the working tree is left at the index with every unstaged change
   removed.

Step 2 is the repository's contribution. A hook that only rewrites the working file is
undone by the rollback checkout and the re-apply succeeds, which is the case pre-commit is
designed for. A hook that also **stages** its output moves the base the rollback depends on.

**Not documented anywhere in this repo.** `grep -rn "Rolling back fixes\|staged_files_only"`
over `docs/` and `templates/` finds nothing, and no known issue mentions the stash-restore
path.

**Workaround / recovery.** pre-commit never deletes its patches. They stay in
`${PRE_COMMIT_HOME:-${XDG_CACHE_HOME:-~/.cache}/pre-commit}/patch<unix-ts>-<pid>`; this
machine currently holds 5,697 of them, including several from 2026-09-16. To recover: pick
the patch whose timestamp matches the failed commit and run `git apply` on it after
resolving `docs/INDEX.md`. Before committing docs, stage or discard any pending edit to
`docs/INDEX.md`, since the failure needs an unstaged hunk in the file the hook stages.

**Fix direction.**

- Stop staging from inside the hook. Regenerate `docs/INDEX.md`, exit non-zero when it
  changed ("INDEX.md regenerated — stage it and re-commit"), and let pre-commit's own
  modified-file handling work. This is the usual pre-commit convention for fixers.
- Failing that, skip the regeneration (with a message) when `docs/INDEX.md` has unstaged
  changes.
- Audit the other `transform-*` hooks for the same in-hook `git add`.
- Add a test: temp repo, unstaged edits to `docs/INDEX.md` and one unrelated file, commit a
  docs change through the real pre-commit, assert the unrelated edit survives.

**Pattern:** a fixer that mutates the index during a stash/restore cycle it does not own.

---
