---
title: "How to create a Claude Code hook"
type: how_to
status: active
created: 2026-05-28
last_updated: 2026-05-28
components:
  - build_pipeline
related_docs:
  - docs/how-to/managing-pre-commit-hooks.md
  - leafcutter-ai/templates/settings.json
---

# How to create a Claude Code hook

This guide explains how to write a new **Claude Code hook** — a Python script
that fires when Claude Code invokes a tool — and register it in the
`templates/settings.json` file so the build pipeline deploys it.

> **Claude Code hooks are not pre-commit hooks.** Pre-commit hooks run when you
> run `git commit`; they are managed by `.pre-commit-config.yaml` and driven by
> the `create-hook` skill. Claude Code hooks fire at Claude's tool-call boundary
> (before or after every `Bash`, `Edit`, `Write`, or `Read` call). The two
> systems are completely separate. If you need to add a pre-commit hook, see
> [managing-pre-commit-hooks.md](managing-pre-commit-hooks.md).

---

## Background: how Claude Code hooks work

When Claude Code executes a tool, it optionally passes control to one or more
external scripts registered in `.claude/settings.json`. Two event types exist:

| Event | When it fires | Can it block? |
|---|---|---|
| `PreToolUse` | Before the tool executes | Yes — exit 0 with `{"decision": "block", ...}` |
| `PostToolUse` | After the tool returns | Yes (block pattern) or no (observational) |

Hooks are Python scripts (or any executable). Claude Code launches each hook
via `bash -c "..."` and writes a JSON payload to the hook's **stdin**. The hook
reads stdin, applies its logic, and exits — either silently or by emitting a
JSON decision object on **stdout**.

---

## Prerequisites

- You have run `build.py` at least once; `.claude/hooks/` and
  `.claude/settings.json` already exist.
- You understand which Claude Code tool triggers your hook (`Bash`, `Edit`,
  `Write`, `Read`, etc.).
- Python 3.9+ is available at `python` on the PATH.

---

## Step 1: Understand the stdin/stdout contract

### Stdin payload (Claude Code → hook)

Claude Code writes a JSON object to stdin on every hook invocation:

```json
{
  "tool_name": "Edit",
  "tool_input": {
    "file_path": "/absolute/path/to/file.py",
    "old_string": "...",
    "new_string": "..."
  },
  "tool_result": null
}
```

Key fields:

| Field | Type | Present in | Description |
|---|---|---|---|
| `tool_name` | string | PreToolUse, PostToolUse | Name of the tool being called (e.g. `"Bash"`, `"Edit"`, `"Write"`, `"Read"`) |
| `tool_input` | object | PreToolUse, PostToolUse | Arguments the tool was called with. Schema varies per tool (see table below). |
| `tool_result` | string or null | PostToolUse only | Output returned by the tool after it ran. `null` in PreToolUse. |

`tool_input` schemas by tool:

| Tool | Relevant fields |
|---|---|
| `Bash` | `command` — the shell command string |
| `Edit` | `file_path`, `old_string`, `new_string` |
| `Write` | `file_path`, `content` |
| `Read` | `file_path`, `limit` (optional), `offset` (optional) |

Always code defensively: use `.get()` with defaults; stdin may be empty or
malformed. When in doubt, **fail open** (exit 0, no output).

### Stdout response (hook → Claude Code)

To block a tool call (PreToolUse only — see note on PostToolUse below), write
this JSON to stdout and exit 0:

```json
{"decision": "block", "reason": "Human-readable explanation for Claude"}
```

To allow the tool call silently, write nothing to stdout and exit 0.

**Important**: the `"decision": "block"` pattern is what Claude Code reads to
inject feedback back to Claude (Claude self-corrects based on the `"reason"`
text). It is valid for both `PreToolUse` (prevents the tool from running) and
`PostToolUse` (injects corrective feedback after the tool ran, but does not
undo the tool's effect).

---

## Step 2: Understand exit codes

Exit codes have different semantics depending on event type:

| Exit code | PreToolUse meaning | PostToolUse meaning |
|---|---|---|
| `0` with no stdout | Allow silently | No action |
| `0` with `{"decision": "block", "reason": "..."}` | Block + inject reason to Claude | Inject corrective feedback to Claude |
| Non-zero (e.g. `1`, `2`) | Fail-open (treated as allow) | Fail-open |

**Fail-open convention (mandatory)**: Claude Code hooks MUST NOT block on
unexpected errors. Wrap your entire `main()` in a `try/except Exception: sys.exit(0)`.
A hook that crashes on a malformed payload would block every single tool call
of that type — which would make Claude Code unusable. Exit 0 silently on any
unexpected path.

---

## Step 3: Understand matchers

The `matcher` field in `settings.json` scopes a hook to specific tool names.
Three matcher forms are supported:

| Form | Example | Matches |
|---|---|---|
| Exact tool name | `"Bash"` | Only `Bash` calls |
| Pipe-separated list | `"Edit\|Write"` | `Edit` or `Write` calls |
| Regex pattern | `"Edit\|Write\|Bash"` | Any of those three tools |

Use the most specific matcher possible. Broad matchers (e.g. `".*"`) fire on
every tool call and add latency to every Claude Code action.

---

## Step 4: Understand the `bash -c` wrapper pattern

Hooks are not invoked directly. Claude Code calls them as:

```
bash -c '<command-string>'
```

The `command` value in `settings.json` is a shell expression, not a bare Python
path. This is intentional:

1. It allows shell variable expansion and `cd` before the Python call.
2. It lets you run a repo-root discovery walk before invoking the hook, so the
   hook works regardless of which directory Claude Code is currently running in.

The standard wrapper pattern used across all built-in hooks is:

```bash
bash -c 'd="$PWD"; while [ ! -d "$d/.claude/hooks" ] && [ "$d" != "/" ]; do d="$(dirname "$d")"; done; python "$d/.claude/hooks/<hook-name>.py"'
```

This walks up the directory tree from `$PWD` until it finds `.claude/hooks/`,
then invokes the hook from that absolute path. This means the hook always runs
from the correct worktree root even when Claude Code's working directory is
inside a subdirectory.

---

## Step 5: Write the hook script

Create your script at:

```
leafcutter-ai/templates/hooks/<hook-name>.py
```

Use this canonical structure (taken from the built-in hooks):

```python
"""
MODULE: <hook-name>.py
GOAL: <PreToolUse|PostToolUse> hook — one-sentence description.
BUSINESS CONTEXT: Why this hook exists and what failure it prevents.
ARCHITECTURE: How it reads stdin and emits its decision.

<PreToolUse|PostToolUse> hook contract:
- Exit 0 with no JSON              = silently allow
- Exit 0 with {"decision": "block", "reason": "..."} = inject feedback to Claude
- Non-zero exit                    = fail-open (allow)
"""
import json
import sys
from pathlib import Path


def main() -> None:
    """Entry point. Reads the hook payload from stdin and emits a decision."""
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)  # fail-open: malformed payload never blocks

    tool_input = payload.get("tool_input") or {}

    # --- Your logic here ---
    # Example: read the file being edited
    file_path = tool_input.get("file_path", "")
    if not file_path:
        sys.exit(0)

    # ... apply your check ...
    violation_found = False  # replace with real check
    reason = ""

    if violation_found:
        print(json.dumps({"decision": "block", "reason": reason}))

    sys.exit(0)  # always exit 0


if __name__ == "__main__":
    main()


"""
====================================================================
DECISION HISTORY
====================================================================
- YYYY-MM-DD HH:MM [Author/Epic]: Initial implementation.
====================================================================
"""
```

**Key patterns to follow:**

- Always wrap `main()` in `try/except Exception: sys.exit(0)`.
- Use `.get()` with defaults for every `payload` field access.
- End every path (blocking and non-blocking) with `sys.exit(0)`.
- Include a `DECISION HISTORY` block at the bottom for audit trail.
- Write to `sys.stderr` for informational messages (not captured by Claude Code);
  write JSON to `sys.stdout` only for the `"decision": "block"` response.

---

## Step 6: Register the hook in `templates/settings.json`

Open `leafcutter-ai/templates/settings.json` and add your hook entry under the
appropriate event type and matcher.

Current structure:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "<ToolName>",
        "hooks": [
          {
            "type": "command",
            "command": "bash -c '<walker-pattern> python \"$d/.claude/hooks/<hook-name>.py\"'",
            "timeout": 10
          }
        ]
      }
    ],
    "PostToolUse": [
      {
        "matcher": "<ToolName>",
        "hooks": [...]
      }
    ]
  }
}
```

Use the full `bash -c` walker pattern from Step 4. The `timeout` field is in
seconds — use 5–10 for lightweight checks, up to 30 for hooks that shell out
to slow processes (git, subprocess). Hooks that exceed their timeout are
treated as fail-open.

### Example: adding a PreToolUse hook on Write

```json
{
  "matcher": "Write",
  "hooks": [
    {
      "type": "command",
      "command": "bash -c 'd=\"$PWD\"; while [ ! -d \"$d/.claude/hooks\" ] && [ \"$d\" != \"/\" ]; do d=\"$(dirname \"$d\")\"; done; python \"$d/.claude/hooks/my_write_guard.py\"'",
      "timeout": 5
    }
  ]
}
```

If there is already a matcher block for the same tool name, **add your hook
entry to the existing block's `"hooks"` array** rather than adding a new
matcher block. Multiple hooks under the same matcher run in array order.

---

## Step 7: Run `build.py` to deploy

After editing `templates/settings.json`, run `build.py` from the repo root to
deploy the updated config and hook script:

```bash
cd leafcutter-ai
python scripts/build.py
```

This copies `templates/hooks/<hook-name>.py` → `.claude/hooks/<hook-name>.py`
and regenerates `.claude/settings.json` from `templates/settings.json`.

Verify the deployment:

```bash
ls .claude/hooks/<hook-name>.py       # hook script deployed
grep "<hook-name>" .claude/settings.json   # hook registered
```

---

## Step 8: Test the hook

Trigger a real tool call that matches your hook's matcher and event type:

**Testing a PreToolUse Edit hook:**
Ask Claude to edit any file. Your hook fires before the edit. Confirm it
blocks correctly (or passes silently) by inspecting Claude's response.

**Testing a PostToolUse Bash hook:**
Ask Claude to run a shell command. Your hook fires after the command returns.
Check that feedback (if any) is injected into Claude's response.

**Manual test (without Claude Code):**
```bash
echo '{"tool_name":"Edit","tool_input":{"file_path":"/tmp/test.md"},"tool_result":null}' \
  | python .claude/hooks/<hook-name>.py
```

Exit 0 with no output = allow. Exit 0 with JSON on stdout = block with that
reason. Check both paths explicitly.

---

## Common mistakes

| Mistake | Symptom | Fix |
|---|---|---|
| Using non-zero exit to block | Hook fires but tool call is NOT blocked — Claude never sees your reason | Use exit 0 + `{"decision": "block", "reason": "..."}` on stdout |
| PostToolUse hook that crashes on malformed `tool_result` | Every post-tool invocation fails; Claude is silently blocked | Wrap all `tool_result` parsing in `try/except` |
| Overly broad matcher (`".*"` or `"Bash\|Edit\|Write\|Read"`) | Hook fires on every tool call; adds latency everywhere | Scope to the specific tool(s) that need the check |
| Forgetting the `bash -c` walker pattern | Hook works in project root but fails inside subdirectories | Copy the walker pattern exactly from Step 4 |
| Writing block reason to stderr instead of stdout | Block decision is not seen by Claude Code; tool proceeds | Block JSON must go to stdout; informational text goes to stderr |
| Blocking on a stdin parse error | Claude Code is blocked when payload is malformed (e.g. empty stdin) | Exit 0 immediately on `json.JSONDecodeError` — never block on parse failures |
| No `DECISION HISTORY` block | Future maintainers cannot trace why the hook was written | Add the `DECISION HISTORY` block before committing |

---

## Reference: built-in hooks summary

| Hook file | Event | Matcher | What it does |
|---|---|---|---|
| `check_commit_ticket_staged.py` | PreToolUse | `Bash` | Blocks `git commit` if the active ticket file has unstaged edits |
| `inline_work_guard.py` | PreToolUse | `Edit\|Write` | Blocks file edits when `.build-feature.lock` exists (enforces supervisor dispatch) |
| `readme_read_guard.py` | PreToolUse | `Edit\|Write` | Blocks edits to certain files if the relevant README has not been read this session |
| `documentation_guard.py` | PreToolUse | `Edit\|Write` | Blocks edits to `.py`/`.sql` files when related architecture docs (L1/L2/L3) have not been updated today |
| `check_ticket_rename_tracking.py` | PostToolUse | `Bash` | Observes `git mv` calls to track ticket renames |
| `readme_marker_recorder.py` | PostToolUse | `Read` | Records a sha256 marker when a README.md file is read |
| `ticket_frontmatter_guard.py` | PostToolUse | `Edit\|Write` | Validates ticket frontmatter immediately after a ticket file is written; injects corrective feedback to Claude on violations |
