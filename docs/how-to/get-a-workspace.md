---
title: "How to get a workspace"
description: "The single way for an agent or a person to get a workspace for a piece of work: one request to the workspace maker, how to read a ready answer, what to do on a refusal, and why asking again is always safe."
type: how_to
category: how-to
status: active
created: 2026-10-13
last_updated: 2026-10-13
components:
  - worktree_manager
  - build_orchestration
related_docs:
  - docs/how-to/clear-a-workspace.md
  - docs/reference/workspace-maker-answer.md
  - docs/architecture/components/worktree-manager.md
  - docs/architecture/diagrams/c3-030-workspace-request-halt-sequence.md
  - docs/architecture/diagrams/c3-031-workspace-request-states.md
---

# How to get a workspace

Every piece of separate work (a ticket, a feature, a quick fix, a scratch session) gets its
own workspace: a full, independent copy of the project that holds its own installed tools.
There is exactly one way to get one: ask the workspace maker. This page is the single place
every instruction about getting a workspace points to. There is no hand-made alternative.

## The request

Run the workspace maker with the `ensure` verb, naming the kind of work and a slug for it:

```bash
python /absolute/path/to/scripts/worktree.py ensure --kind <kind> --slug <slug>
```

- `<kind>` is one of `ticket`, `feature`, `ac`, `fastlane`, `epic`, `scratch`.
- `<slug>` names the work. Every workspace is called `<kind>/<slug>`. Older spellings (for
  example `EPIC-<Name>`) are accepted and reach the same workspace.
- The script path is the maker's installed location. If you do not know it, run the
  maker's `where` verb from wherever you can reach it; the answer's `path` is the script.

The same request works from the project's top folder, from the folder above it, and from
inside another workspace. The maker finds the project itself; you never change folder first.
Workspaces live in the project's sibling folder `<project-dir-name>-worktrees/`, outside
the main copy. Do not build that location from this pattern; take it from the answer.

## Reading a ready answer

The maker prints exactly one JSON object on standard output. A ready answer has
`"status": "ok"` and exit code 0. The workspace's location is its `workspace_path` field:

```json
{"status": "ok", "code": "OK", "workspace_path": "<location>", "branch": "<kind>/<slug>"}
```

Take the location from `workspace_path` of an ok answer only. Never take it from an agent's
own words, and never from the folder you happen to be in. Work inside that folder from then
on. Every other field is listed in [the answer reference](../reference/workspace-maker-answer.md).

To read the location of an existing workspace back later without changing anything:

```bash
python /absolute/path/to/scripts/worktree.py locate --kind <kind> --slug <slug>
```

## What to do on a refusal

Any answer that is not `"status": "ok"` is a stop. The `code` and `message` name the cause.

1. Stop. Do not start work, and do not guess a location.
2. Remedy the cause the answer names (for example, deliver the work it lists, supply the
   config it names, or name the one line of work it says is ambiguous).
3. Ask again with the same request.

Asking again for the same work is always safe. A workspace that is already ready is
re-readied and returned as it is, a half-made one is finished in place, and one that holds
other work is left untouched and refused. See
[the state diagram](../architecture/diagrams/c3-031-workspace-request-states.md) and
[the halt sequence](../architecture/diagrams/c3-030-workspace-request-halt-sequence.md).

Every code and what it means is in [the answer reference](../reference/workspace-maker-answer.md).

## When you are done

Clearing a workspace has its own safeguard for work that was never delivered. See
[How to clear a workspace](clear-a-workspace.md).
