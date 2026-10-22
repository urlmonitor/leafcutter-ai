---
allowed-tools: Bash(python *)
description: Get an isolated workspace for a piece of work by running the one workspace maker and relaying its JSON answer unchanged. Use when you need a workspace for a ticket, feature, AC, fast-lane run, epic or scratch session.
name: feature
---

# Workspace (the one maker)

Get a workspace for: **$ARGUMENTS**

This skill is THE workspace skill. It publishes exactly one thing: the command
that runs the workspace maker. It has no recipe of its own, and no step in it
asks you to create, copy, set up, link or repair a workspace by steps of your
own choosing. The maker does all of that, the same way for every caller.

## Step 1 — Work out the work identity

Pick the `--kind` (`ticket`, `feature`, `ac`, `fastlane`, `epic` or `scratch`)
and the `--slug` (the work's name) from `$ARGUMENTS`. If `$ARGUMENTS` is empty,
ask the user what they want to work on.

## Step 2 — Run the maker

Run the maker as ONE command, by the absolute path of the deployed
`worktree.py` (the install's `scripts/worktree.py`; the path `worktree.py
where` prints). Never use a cwd-relative path and never chain commands:

```bash
python <absolute-install-root>/scripts/worktree.py ensure --kind <kind> --slug <slug> --repo-root <absolute-project-root>
```

If the work is a ticket, add `--ticket <absolute path of the ticket's main copy>`.

- **Non-zero exit:** stop. Surface the maker's answer verbatim to the user. Do
  not retry with a hand-made workspace and do not carry on in the current
  checkout.
- **Exit 0:** the one JSON object on stdout is the answer. Relay it word for
  word; do not edit, trim or re-shape it. Hand it to whatever comes next as
  `args.workspace`, and work only inside the `workspace_path` it names.

## Step 3 — Finish

Tell the user the `workspace_path` and `branch` from the answer, and remind them
to run `/ship` when the work is complete. Asking for the same work again returns
the same workspace; the maker resumes it.
