---
description: "Fast in-place bug-fix pipeline. Accepts a structured diagnosis (target_file, location_hint, symptom, root_cause) and drives: AC creation → test-first (red) → fix (python-coder) → green phase → commit → close. No new worktree or branch is created. Escalates to /build-feature when scope expands beyond the target file."
---

# /quick-fix — Fast In-Place Bug Fix

This command is the entry point for the quick-fix workflow. It is the
**current-worktree** alternative to `/build-feature` for focused, single-file
bug fixes that do not require a new branch or full ticket lifecycle.

## When to use /quick-fix vs. /build-feature

| Condition | Use |
|-----------|-----|
| You have a clear diagnosis (file, location, root cause) and the fix touches one file | `/quick-fix` |
| The fix spans multiple files, requires design decisions, or needs a PR review cycle | `/build-feature` |
| You want a new isolated worktree and clean branch | `/build-feature` |
| You want the fix committed on the current branch immediately | `/quick-fix` |

## Input formats

**Natural language:**
```
/quick-fix In scripts/build_helpers.py line 42, _resolve_precommit_cmd() returns
a non-executable path because the executability probe is missing.
```

**Structured:**
```
/quick-fix {
  "target_file": "scripts/build_helpers.py",
  "location_hint": "line 42 / _resolve_precommit_cmd()",
  "symptom": "returns a non-executable path",
  "root_cause": "executability probe is missing"
}
```

Both formats are accepted. The skill parses them into four fields:
`target_file`, `location_hint`, `symptom`, `root_cause`.

## What this command does

Loads `.claude/skills/quick-fix/SKILL.md` and executes the six-phase pipeline:

1. **Phase 0 — Guards**: worktree invariant check, no-isolation check, uncommitted-changes guard.
2. **Phase 1 — AC Creation**: writes a permanent `docs/acceptance-criteria/` YAML entry.
3. **Phase 2 — Test-first**: dispatches `test-writer`, verifies the test fails (red phase).
4. **Phase 3 — Fix**: dispatches `python-coder` with a single-file constraint.
5. **Phase 4 — Green phase**: verifies the test now passes.
6. **Phase 5 — Commit**: dispatches `commit` agent with exact staging instructions.
7. **Phase 6 — Close**: pushes to origin, checks for open PR, prints completion summary.

Escalation to `/build-feature` is offered automatically if `python-coder` modifies more
than the target file, or if the red-phase failure pattern diverges from the diagnosis.

## What this command does NOT do

- Does not create a new worktree or branch.
- Does not open a PR autonomously (it shows a link if none exists).
- Does not scaffold a full ticket or epic.
- Does not bypass the `commit` agent's pre-commit hook loop.

---

Load `.claude/skills/quick-fix/SKILL.md` and execute the workflow with `$ARGUMENTS` as the diagnosis input.
