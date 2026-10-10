---
title: "KI-BO-20261009-fast-lane-changelog-publishes-absolute-local-paths — the fast lane writes the coder's files_modified into its changelog entry exactly as reported, so 12 of the 15 fast-lane entries on main publish a contributor's home directory and worktree name"
description: "low — build_changelog_payload() in scripts/build_orchestration/_fl_changelog.py joins files_modified verbatim into the entry's description (\"Files modified: ...\"). The coder phase in fast-lane-ship.js is never told to report repo-relative paths, so it usually reports absolute ones. git grep finds /home/ in 13 changelogs/ files on main 5caa16ca. 12 are this pattern, out of 15 fast-lane entries in total. The 13th is a hand-written quotation. Most recent: the 2026-10-08 GE-118d entry merged in PR #1053. The same absolute paths also never match the fast lane's repo-relative changelog-exempt prefixes. That second consequence is inferred."
type: reference
category: reference
status: active
created: '2026-10-09'
last_updated: '2026-10-09'
components:
  - build_orchestration
  - changelog
related_docs:
  - docs/known-issues/build-orchestration.md
  - docs/known-issues/README.md
  - docs/known-issues/changelog.md
---

# KI-BO-20261009-fast-lane-changelog-publishes-absolute-local-paths — the fast lane writes the coder's `files_modified` into its changelog entry exactly as reported, so 12 of the 15 fast-lane entries on main publish a contributor's home directory and worktree name

> **Why this register.** The path is composed in the fast lane's own changelog phase
> (`scripts/build_orchestration/_fl_changelog.py`, called from `fast-lane-ship.js`), not in the
> changelog tooling, which writes whatever payload it is given. `components:` names `changelog`
> so it can be found from that side. Index: [build-orchestration.md](../build-orchestration.md).

- **Severity:** low. No build or gate breaks. But the entries are shipped, release-note-feeding
  files, and each one publishes a local username, home-directory layout and worktree name.
- **Status:** open, no AC.
- **Occurrences:** 12 entries on main, from 2026-08-31 to 2026-10-08 (list below).
- **First seen:** 2026-08-31 (oldest affected entry) · **Last seen:** 2026-10-08 (PR #1053,
  merge `fbf0c5223`)
- **Where:** the description is composed at `scripts/build_orchestration/_fl_changelog.py:145-151`:

  ```python
  files_text = ", ".join(files_modified)
  description = (
      f"Fast-lane build of {target_ac} (branch {branch}). "
      f"Built acceptance criteria: {built_ids_text}. "
      f"Files modified: {files_text}."
  )
  ```

  `templates/workflows-js/fast-lane-ship.js:1608` takes `coderResult.files_modified` unchanged
  and passes it at `:1617-1620` (`changelog_payload ... --files-modified "${filesModified.join(",")}"`).
  The coder's return contract at `:1412` is `"files_modified": ["<path>", ...]` and says nothing
  about relative versus absolute paths. `fast-lane-ship.js` does contain a "Fast-lane build of"
  string at `:1906`, but that is the run's terminal message, not the changelog.

## The instance that prompted this

`changelogs/2026-10-08-1746-a-document-s-path-bearing-frontmatter-entries-are-resolved-whichever-of-the-two-accepted-shapes-they-use.md:9`
(added by `20cfaa48b`, merged in PR #1053):

```text
description: "Fast-lane build of GE-118d (branch fast-lane/ge-118d). Built acceptance criteria: GE-118d, GE-118d-1, GE-118d-2. Files modified: /home/henzeh/projects/leafcutter/worktrees/ge-118d/scripts/frontmatter_path_resolver.py, /home/henzeh/projects/leafcutter/worktrees/ge-118d/templates/scripts/commit_guardian/frontmatter_validators.py."
```

## It is a pattern, not one entry (measured on origin/main `5caa16ca`)

`git grep -l "/home/" -- changelogs/` lists **13** files. Reading each matching line:

- **12** are the fast-lane `Files modified: /home/...` form. Their dates are 2026-08-31-1229,
  2026-09-01-1253, -1425 and -1630, 2026-09-07-1017, -1131, -1308 and -1800, 2026-09-08-1005
  (path under `.leafcutter/worktrees/`), 2026-09-09-1024, 2026-09-14-1322, and 2026-10-08-1746.
- **1** (`2026-09-21-1620-the-fast-lane-deleted-a-remote-branch...`) is hand-written prose that
  quotes a path a run reported. It is not this defect.

`git grep -l "Fast-lane build of" -- changelogs/` lists **15** fast-lane entries. The three
without absolute paths (2026-09-17-0727, 2026-09-25-1201 and 2026-09-25-1357) show that the form
of the path depends on what the coder agent happened to report that run. Two of those three list
relative `Files modified:` paths, and the third has a hand-written description. No code
normalises the paths in either direction.

## A second consequence (inferred from code, not observed)

The same unnormalised list decides whether a changelog is required. `fast-lane-ship.js:1609-1612`
keeps the paths that do **not** start with one of `CHANGELOG_EXEMPT_PREFIXES` (`changelogs/`,
`tickets/`, `docs/acceptance-criteria/`, `docs/known-issues/`, `:444-449`). An absolute path never
starts with a repo-relative prefix, so a run that touched only exempt files but reported them
absolutely would be told it owes a changelog entry. The Python twin
`compute_changelog_requirement()` documents its input as "repo-relative"
(`_fl_changelog.py:60-62`) and would have the same blind spot. Nobody has seen this happen. It
follows from the code.

## Detection

```bash
git grep -n "Files modified: /" -- changelogs/
```

Any hit is this defect.

## Workaround

Before merging a fast-lane PR, edit the generated entry's `description` so its paths are
repo-relative. The existing 12 entries can be corrected the same way in a docs-only commit.
Changelog entries are exempt from the changelog-presence gate.

## Fix direction

Make paths repo-relative before they are written. The narrowest place is
`build_changelog_payload()`: strip the worktree root (the run already knows `worktreePath`) or
use `os.path.relpath` against the repository root for each entry. Do the same normalisation once
in `fast-lane-ship.js` before `:1609`, so that the exempt-prefix filter and the payload see the
same repo-relative list. Also have the coder contract at `:1412` ask for repo-relative paths. Add
a test that feeds an absolute worktree path into `build_changelog_payload()` and asserts that no
`/home/`, drive letter, or worktree name reaches the description.

**Pattern:** a field filled from an agent's free-form report and written verbatim into a
published artifact. Whatever local detail the agent included gets shipped.
