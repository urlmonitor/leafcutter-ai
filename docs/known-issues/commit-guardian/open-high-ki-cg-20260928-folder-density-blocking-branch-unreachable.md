---
title: "KI-CG-20260928-folder-density-blocking-branch-unreachable — check-folder-density computes its before-commit snapshot with git ls-files, which reads the post-git-add index, so before always equals after and the one blocking branch can never be taken"
description: "high — the check is designed to block only the commit that newly pushes a folder over the density limit. That is the one case it structurally cannot detect: its before-snapshot is taken after staging, so a newly-crossing folder measures as already-over and lands in the warning branch. The single return 1 is dead code."
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - commit_guardian
  - precommit_hooks
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/commit-guardian/open-high-ki-cg-20260928-ticket-test-requirements-gate-reads-stdin-nothing-writes.md
---

# KI-CG-20260928-folder-density-blocking-branch-unreachable — the before-snapshot is taken after staging, so nothing ever newly crosses

- **Severity:** high. The gate's only blocking path is unreachable. It still prints a warning, so
  it does not look dead — it looks lenient.
- **Status:** open — no AC.
- **Occurrences:** 1 (found by the `GE-120b-2-i` provoking-fixture sweep, 2026-09-28).
- **First seen:** 2026-09-28 · **Last seen:** 2026-09-28
- **Where:** `templates/scripts/commit_guardian/check_folder_density.py` — `:130`
  (`["git", "ls-files"]`), `:277-289` (the before/after snapshots), `:237-243`
  (`_classify_folders`), `:302` (the sole `return 1`).

## Mechanism

The design is deliberately narrow and correct in intent: block only the commit that **newly**
pushes a folder past `MAX_FILES_PER_FOLDER`, and merely warn about folders that were already
over. `_classify_folders` encodes exactly that:

```
if after_count > MAX_FILES_PER_FOLDER:
    if before_count > MAX_FILES_PER_FOLDER:
        warnings.append(...)     # already over — do not block
    else:
        violations.append(...)   # THIS commit crossed the line — block
```

Blocking therefore requires `before_count <= MAX < after_count`.

The "before" snapshot is built at `:277-280` from `get_all_tracked_files()`, which shells out to
plain **`git ls-files`**. That lists the **index**, not `HEAD`. By the time any pre-commit hook
runs, `git add` has already happened — so every newly staged file is *already* counted in the
"before" snapshot. The code's own comment at `:279` says "before staged additions", which is
what makes this hard to spot by reading: the comment states the intended semantics, and the call
beneath it does something else.

Lines `:283-286` then add the staged files into the set to form "after" — but they are already
members, so the set is unchanged. `after_counts == before_counts` for exactly the case the gate
exists to catch, `before_count > MAX` is true, and control lands in the warning branch. The
`return 1` at `:302` is unreachable for any newly-added file.

## Evidence

The `GE-120b-2-i` fixture staged 16 new files into a brand-new folder, well over the limit, in a
folder that did not previously exist at all — the most unambiguous "this commit crossed the line"
case constructible. The check reported:

```
⚠️  PRE-EXISTING DENSITY: scripts/ge120fixture/density/ ...
    (Folder was already over the limit — not blocking this commit)
```

A folder created by this very commit was described as pre-existing and already over. Exit 0.

## Scope — this is not a harness artifact

The mechanism is identical under a real `git commit`: `git add` precedes hook execution there
too, so `git ls-files` is equally post-staging. Nothing about the `GE-120c-1` second-working-copy
harness causes or amplifies this. It should be reproduced once under a real commit before the fix
lands, but the reasoning does not depend on the harness.

## Fix direction

1. **Take the before-snapshot from `HEAD`, not the index** — `git ls-tree -r --name-only HEAD`
   answers the question the code's comment already claims to be asking. The after-snapshot stays
   as it is.
2. **Handle the no-HEAD case explicitly** (initial commit, unborn branch): report could-not-check
   per `GE-120a-1` rather than defaulting to an empty before-set, which would flip the gate from
   never-blocking to blocking-everything.
3. **Add a negative control that must block** — a fixture staging N+1 files into a folder absent
   from `HEAD`. Without one this regresses silently, exactly as it has until now.

## Related

`KI-CG-20260928-ticket-test-requirements-gate-reads-stdin-nothing-writes` — the sibling found in
the same sweep: also registered, also always exit 0, by a different mechanism.

**Pattern:** a check that measures "before" from a source already mutated by the operation it is
trying to judge — so the change it exists to detect is invisible to it, and the code comment
describing the intended semantics is the only place the correct behaviour is written down.
