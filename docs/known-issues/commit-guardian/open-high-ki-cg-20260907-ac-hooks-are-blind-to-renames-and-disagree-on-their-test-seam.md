---
title: "KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam"
description: "KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-21'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260907-ac-hooks-are-blind-to-renames-and-disagree-on-their-test-seam

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 1 (found while performing an AC id migration; the defect is structural, not incidental)
- **First seen:** 2026-09-07 · **Last seen:** 2026-09-07
- **Where:** `templates/scripts/commit_guardian/check_ac_schema.py:349`,
  `check_ac_parent_covered_by.py:182`, `check_ac_limits.py:354` — the staged-file query each
  performs, and the environment variable each accepts as its test seam

**Two defects in one place. The first is the expensive one.**

#### 1. Every AC hook is blind to a renamed file

All three hooks discover their input with the same query:

```
git diff --cached --name-only --diff-filter=AM
```

`AM` selects **A**dded and **M**odified. Git classifies a rename as **R**, so a renamed file is
in none of the three. Measured in a scratch repository, staging one rename of a file under
`docs/acceptance-criteria/`:

```
$ git diff --cached --name-status
R086    docs/acceptance-criteria/OLD-1.yaml    docs/acceptance-criteria/NEW-1.yaml

$ git diff --cached --name-only --diff-filter=AM
                      <- empty. The record is invisible to every AC hook.

$ git diff --cached --name-only
docs/acceptance-criteria/NEW-1.yaml        <- visible without the filter
```

**Why this is high and not medium.** Renaming is not an exotic operation in this store — it is
what an *id migration* is, because a record's parent is derived from its id string, so moving a
record between parents renames its file. The AC-tree-split procedure the repository documents
and actively uses therefore produces exactly the change shape that no AC guard examines. A
split can relocate a record into a parent that is already at its child cap, break a
`covered_by` back-link, or introduce a dependency cycle, and `check_ac_limits`,
`check_ac_parent_covered_by` and `check_ac_schema` will each exit 0 having been handed nothing.

This is the family's signature failure re-appearing at the input stage rather than the logic
stage. The hooks are correct; they are simply never given the file. Their silence is not a pass.

Observed live: a migration of `BP-100n-4` (+ two children) into `BP-1600a-2` staged three
renames alongside 42 ordinary edits. Git detected all three as renames at 92–94% similarity.
The three moved records were checked only because the operator drove them through the
environment seam by hand, having anticipated the gap. A normal commit would not have.

#### 2. Four hooks, two seam names, and one with extra parsing

The environment override used for testing is not consistent, so a control fed to the wrong hook
is silently discarded:

| hook | seam variable |
|---|---|
| `check_ac_schema.py` | `HOOK_TEST_STAGED_FILES` (`:324`) |
| `check_ac_parent_covered_by.py` | `HOOK_TEST_FILES` |
| `check_ac_circular_deps.py` | `HOOK_TEST_FILES` |
| `check_ac_limits.py` | `HOOK_TEST_FILES`, split on **newlines only**, then filtered to paths containing `docs/acceptance-criteria` |

An unrecognised variable is not an error. It falls through to the real `git diff --cached`,
which for an unstaged edit yields no AC files, and the hook exits **0 having examined nothing**.
`check_ac_schema.py` additionally reads `HOOK_TEST_FILES_MODIFIED` (`:706`) for its second
phase, so that one file alone has two seams with different meanings.

The practical consequence is that the obvious way to test a hook produces a confident false
pass. During the migration above, three separate attempts to verify a hook were no-ops before
the seam was read from source — including one invocation written specifically to *guard*
against no-op verification, and a colon-joined control handed to `check_ac_limits`, which
discards anything not newline-separated.

#### 3. `check_ac_limits` resolves the store from `cwd`, so the *right* seam with the *right* paths still passes silently

Distinct from #2, and it survives fixing #2. Feed `check_ac_limits.py` its correct seam variable
(`HOOK_TEST_FILES`) with correct, existing, absolute paths, and it still exits 0 having checked
nothing — because `_find_ac_store_root()` (`:694`) resolves the store from `cwd`, while the match
at `:711` is `str(node.source_path).endswith(staged_path.lstrip("/"))`. Run from any directory
whose git root is not the tree holding those files and the loaded nodes come from a *different*
store, nothing matches, and `:716` returns 0 with no output at all.

So the hook has two silent zero-exits that cannot be told apart from the outside: "no AC files
staged" (`:691`) and "your files matched nothing I loaded" (`:716`). Only the second is a defect,
and it is the one an operator hits while verifying.

Reproduced 2026-09-21 on `ac-authoring/tq-600-suite-speed`, against a tree with three live
`child_limit_override`s:

```
# absolute path, cwd outside the worktree
$ HOOK_TEST_FILES=<abs>/TQ-600a.yaml python <worktree>/.leafcutter/.../check_ac_limits.py
exit: 0                                    # <- no output. examined nothing.

# same file, worktree-relative, cwd inside the worktree
$ env --chdir=<worktree> HOOK_TEST_FILES=docs/acceptance-criteria/.../TQ-600a.yaml \
    python .leafcutter/.../check_ac_limits.py
[check-ac-limits] OVERRIDE ACTIVE: parent 'TQ-600a' (L1) has 7 L2 children; ...
exit: 0
```

Both exit 0. Only the second one looked. A control run with the override *removed* and 7 children
also exited 0 silently from the wrong cwd — so this cannot be caught by "did the hook pass?", only
by "did the hook say what it examined?".

The real pre-commit path is unaffected: pre-commit runs from the repo root and the paths from
`git diff --cached` are already root-relative. This is a *verification* defect — it makes the
obvious way to check a guard report a confident false pass, which is how #1 and #2 above went
unnoticed.

**Remediation.**

1. Change the staged-file query to include renames. `--diff-filter=AMR` with `--name-only`
   reports the destination path, which is the one that needs checking. Verify by staging a
   rename and confirming the hook names the new path — a passing run over an empty set is the
   defect, not the proof.
2. Extract the staged-file discovery into one shared helper the four hooks import, rather than
   four copies of the same query. The rename gap exists four times because the query does.
3. Converge on ONE seam variable name, and make an **unrecognised** `HOOK_TEST_*` variable a
   hard error rather than a silent fall-through. A typo in a test seam must not read as a pass.
4. When the census work under `BP-1600a-2` lands, the population it walks should come from the
   same helper, so the two cannot drift.
5. (for #3) Make the two silent zero-exits distinguishable. `check_ac_limits.py:716` — staged
   paths that matched no loaded node — must say so on stderr, naming how many paths it was given
   and how many it resolved, rather than returning 0 mutely; "0 of 1 staged paths resolved against
   the store at `<root>`" turns the false pass into an obvious operator error. The same applies to
   the sibling hooks once they share the helper from item 2. Normalising the staged path against
   the resolved store root before comparing would fix the absolute-path case outright, but the
   reporting matters more than the normalisation: a hook that cannot examine its input must not be
   able to say nothing about it.

**Related.** `KI-CG-034` (a check that examined nothing exiting 0). The CLAUDE.md note under
"AC-store commits — stage the parent alongside the child", which already records that these
hooks see only the index and that several ignore `argv` — this entry adds that the index query
itself omits a whole change class. `docs/reference/false-green-mechanisms.md` → M9 and the
`unit_tests/README.md` §8 rule that a check which examined nothing must not look like a check
that found nothing.

**Pattern:** a guard whose logic is sound and whose *input query* silently excludes the exact
operation the surrounding procedure tells you to perform.

---
