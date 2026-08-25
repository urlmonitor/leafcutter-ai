---
description: "Fast bug-fix pipeline. Accepts a structured diagnosis (target_file, location_hint, symptom, root_cause) and drives: worktree self-isolation (when needed) → AC creation → test-first (red) → fix (python-coder) → green phase + mutation proof → commit → changelog entry → close (push + confirmed PR). Operates in place when the cwd is already an isolated, non-default-branch worktree; otherwise creates one automatically via setup_ticket_worktree.py before doing any work. Escalates to /build-feature when scope expands beyond the target file."
---

# /quick-fix — Fast Bug Fix, Isolated When It Needs To Be

This command is the entry point for the quick-fix workflow: a focused,
single-file bug fix, backed by a formal acceptance criterion and a
test-first proof, that ends with a pushed branch and (on confirmation) an
open PR.

Isolation is **conditional, not absent**. If the session is already inside a
git worktree on a branch other than `main`/`master`, quick-fix operates in
place, exactly as it always has. If the session is not inside a git repo at
all (common when the cwd is an untracked workspace parent), or is on
`main`/`master` (which is PR-only in this repo — a direct commit cannot be
pushed), quick-fix creates an isolated worktree for you via the repository's
canonical `setup_ticket_worktree.py create-only` script before doing anything
else, then proceeds exactly as it would have in place.

## When to use /quick-fix vs. /build-feature

| Condition | Use |
|-----------|-----|
| You have a clear diagnosis (file, location, root cause) and the fix touches one file | `/quick-fix` |
| The fix spans multiple files, requires design decisions, or needs a full ticket lifecycle | `/build-feature` |
| You want a single AC and a lightweight, self-contained diff, letting isolation happen automatically only when needed | `/quick-fix` |
| You want the fix committed on the current branch immediately, when you are already on a non-default-branch worktree | `/quick-fix` |

`/quick-fix` never scaffolds a full ticket or epic — that stays the dividing
line from `/build-feature`, not the presence or absence of a worktree.

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

Invokes the `quick-fix.js` workflow script (deterministic JS control flow) which
enforces the exact phase sequence:

1. **Guards and self-isolation**: determines whether the cwd is already a
   usable, non-default-branch worktree; if not, creates one via
   `setup_ticket_worktree.py create-only` (after a stale-local-`main`
   pre-check), then checks the target file for uncommitted changes.
2. **AC Creation**: writes a permanent AC YAML entry into the hierarchical
   `docs/acceptance-criteria/` store, at the correct level (L2, or an L3
   technical-constraint child when the parent's L2 slot cap is already
   full), with a back-link staged on its parent.
3. **Red Phase**: dispatches `test-writer`, then verifies the test fails
   under `AC_ENFORCE_STRICT=1` (never the default invocation — see the
   skill for why the default masks a red result).
4. **Fix**: dispatches `python-coder` with a single-file constraint.
5. **Green Phase + Mutation Proof**: verifies the test now passes under
   `AC_ENFORCE_STRICT=1`, then reverts the fix and confirms the test goes
   red again before restoring it — proof the test is actually coupled to
   the fix, not just green by coincidence.
6. **Commit**: dispatches the `commit` agent to stage the AC(s), test, and
   fix together.
7. **Changelog**: dispatches `changelog-agent` to author an entry (a
   required CI status check on `main`), committed separately before push.
8. **Close**: pushes, then — after explicit user confirmation — opens a PR
   via `gh pr create` (switching to the non-EMU `gh` account first, and
   writing the PR body to a file to avoid shell-interpolating identifiers
   in the body).

The workflow halts with `status: "blocked"` when user input is required
(stale-main, no matching AC parent, divergence warnings, scope expansion,
test failures, mutation-proof failure, or the PR confirmation gate).
Escalation to `/build-feature` is offered automatically if scope expands
beyond the target file.

## What this command does NOT do

- Does not scaffold a full ticket or epic.
- Does not force isolation when the current worktree is already suitable —
  it only creates a new one when the cwd genuinely cannot be used in place.
- Does not merge a PR — opening one is confirmation-gated and always
  precedes the user's own merge decision.
- Does not bypass the `commit` agent's pre-commit hook loop, and never calls
  `git commit` directly.
- Does not silently raise an AC child-count cap (`child_limit_override`) or
  split an AC tree — both require a Stop-and-Ask.

---

Parse `$ARGUMENTS` into a diagnosis object. If the input is natural language, extract the four fields (target_file, location_hint, symptom, root_cause) from the sentence. If structured JSON, use directly.

Then invoke the workflow:

```
Workflow(name: "quick-fix", args: { target_file, location_hint, symptom, root_cause })
```

If `quick-fix.js` is not available (pre-v2.1.154 install), fall back to loading
`.claude/skills/quick-fix/SKILL.md` and executing the workflow manually with
`$ARGUMENTS` as the diagnosis input.
