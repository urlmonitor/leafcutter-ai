---
allowed-tools: Bash(python3 *), Read
description: Get the isolated workspace for a piece of work by running the one workspace
  maker, and relay its JSON answer unchanged. This is THE workspace skill; every other
  entry point runs the same maker the same way.
name: feature
---

# Get a Workspace (the one workspace skill)

Get the isolated workspace for: **$ARGUMENTS**

This skill makes no workspace by its own steps. There is exactly one workspace
maker, `worktree.py`, deployed at `<project-root>/.leafcutter/scripts/worktree.py`.
It fetches, builds, checks readiness, and answers with one JSON object. This skill
runs it once and hands the answer on.

> **`/quick-fix` note:** `/quick-fix` runs the same maker from its own Phase 0. It
> never loads this skill.

## Routing

Inspect `$ARGUMENTS` to pick the work identity:

- **A ticket path inside an epic folder** (`tickets/.../EPIC-<NAME>/<NN>_*.md`):
  `kind` is `epic` and `slug` is `EPIC-<NAME>`. The whole epic shares one workspace.
- **Anything else** is a free-form feature name: `kind` is `feature` and `slug` is
  the name, lowercased, with spaces turned into hyphens.

If `$ARGUMENTS` is empty, ask the user what they want to work on, then stop.

## Run the maker (one command)

`<project-root>` is the absolute path of the project's main checkout.

```bash
python3 <project-root>/.leafcutter/scripts/worktree.py ensure --kind <kind> --slug <slug> --repo-root <project-root>
```

The maker is idempotent: asking again for the same work returns the same workspace.

## After the maker returns

- **Non-zero exit, or stdout that is not one JSON object:** stop. Show stderr and
  stdout word for word. The answer carries a `code` that names the reason. Do not
  carry on with the work, and do not try to make or mend a workspace by other means.
- **Exit 0:** the answer has `status: ok`. Take `workspace_path` and `branch` from
  it, tell the user both, and do the rest of the work inside `workspace_path`.
  When a workflow needs the workspace, pass the whole parsed answer on as
  `args.workspace`, word for word.

## Important

- The maker bases every workspace on `origin/main` as fetched when it runs.
- One piece of work has one workspace. Epic work reuses its epic workspace.
- Removing a workspace is the maker's `remove` verb, which refuses while the workspace
  holds work that has not reached the shared project.
