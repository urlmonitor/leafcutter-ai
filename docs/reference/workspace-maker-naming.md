---
title: "Reference: Workspace Maker Work Identity and Naming"
description: "Branch and folder naming per kind, slug normalisation rules and the epic spellings that name one workspace, for the one workspace maker (worktree.py); consult it when predicting the branch or folder a slug produces."
type: reference
status: active
created: 2026-10-16
last_updated: 2026-10-16
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/reference/workspace-maker-interface.md
  - docs/reference/workspace-maker-answers-and-codes.md
  - docs/architecture/adrs/ADR-070-single-workspace-maker-and-resolver.md
---

> **Parent document:** [workspace-maker-interface.md](workspace-maker-interface.md)

# Workspace Maker Work Identity and Naming

Lookup tables for how the maker turns a kind and a raw slug into a branch, a folder name and a workspace path. Verbs and flags are in the parent document.

---

## Work Identity and Naming

Source: `workspace_core.py` (`_PREFIX`, `_ALIASES`, `_WORD_FOLDED`, `_CAMEL_BOUNDARY`, `normalize_slug`, `branch_for`, `dirname_for`, `make_plan`).

| Kind | Branch | Landing folder name for slug `S` |
|---|---|---|
| `ticket` | `ticket/S` | `ticket-S` |
| `feature` | `feature/S` | `feature-S` |
| `ac` | `ac/S` | `ac-S` |
| `fastlane` | `fastlane/S` | `fastlane-S` |
| `epic` | `EPIC-S` | `EPIC-S` |
| `scratch` | none (detached at base) | `scratch-S` |

| Normalisation rule | Behaviour |
|---|---|
| Alias strip | For kind `epic`, a leading `EPIC-` or `epic/` (case-insensitive) is removed. Each alias is tried in turn. |
| Word folding | For kind `epic` only, a hyphen is inserted at each lower-case-or-digit to upper-case boundary, then the whole slug is lower-cased. Other kinds keep their case. |
| Character class | Runs of characters outside `A-Za-z0-9._-` become `-`. |
| Dots | Runs of two or more `.` collapse to one; leading and trailing `-` and `.` are trimmed. |
| `.lock` suffix | A trailing `.lock` is removed. |
| Empty result | `USAGE`. |

The workspace path is `<project parent>/worktrees/<folder name>`.

### Epic spellings that name one workspace (BO-4300a-2)

Every spelling in the first column normalises to the slug in the second, so `ensure`, `locate` and `list` resolve all of them to one workspace (`EPIC-files-stay-workable`) and one branch of the same name.

| Spelling a route uses | Used by | Normalised slug |
|---|---|---|
| `EPIC-FilesStayWorkable` | feature skill epic route | `files-stay-workable` |
| `epic/files-stay-workable` | build-feature route | `files-stay-workable` |
| `Files Stay Workable` | the epic's display title | `files-stay-workable` |
| `FilesStayPortable` | a different epic | `files-stay-portable` |

Matching is on the whole normalised slug. It is never a prefix or substring match, so `Files Stay` does not select `Files Stay Workable`. A repeat request for an existing identity answers ok with the existing `workspace_path`. It creates no second workspace or branch and moves no commit on the existing branch.

```mermaid
flowchart LR
    A["EPIC-FilesStayWorkable"] --> N["normalize_slug(epic)"]
    B["epic/files-stay-workable"] --> N
    C["Files Stay Workable"] --> N
    N --> S["files-stay-workable"]
    S --> W["worktrees/EPIC-files-stay-workable"]
    S --> BR["branch EPIC-files-stay-workable"]
```

Limit: a title whose words are already lower-case with no separators (for example `filesstayworkable`) cannot be split and names a different identity.
