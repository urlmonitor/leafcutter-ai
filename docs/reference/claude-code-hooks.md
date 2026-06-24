---
title: "Reference: Claude Code Hooks"
description: "Reference guide for Claude Code PreToolUse and PostToolUse hooks — hook types, registration format, exit-code contract, and the fail-open convention."
type: reference
status: active
created: 2026-05-28
last_updated: 2026-06-18
components:
  - "build_pipeline"
related_docs:
  - "docs/how-to/creating-a-claude-code-hook.md"
  - "docs/how-to/managing-pre-commit-hooks.md"
---

# Reference: Claude Code Hooks

Claude Code hooks are Python scripts registered in `.claude/settings.json` that
run automatically before or after Claude Code tool calls. They enforce
project-specific rules (e.g. README awareness, ticket frontmatter validity,
commit hygiene) at the session level — before any code reaches a pre-commit hook
or CI gate.

> **Naming collision:** This page covers *Claude Code hooks* (PreToolUse /
> PostToolUse events in `.claude/hooks/`). These are distinct from *pre-commit
> hooks* (scripts in `.git/hooks/` or managed by `pre-commit`). For pre-commit
> hooks see [Managing Pre-Commit Hooks](../how-to/managing-pre-commit-hooks.md).

---

## Hook Catalogue

The table below lists every hook currently deployed in `.claude/hooks/` (built
from `templates/hooks/` by `build.py`).

| Hook Name | Event Type | Matcher | Description | File |
|---|---|---|---|---|
| `check_commit_ticket_staged` | PreToolUse | `Bash` | Blocks `git commit` when the active ticket file has unstaged modifications, ensuring phase-agent sign-offs are captured in the commit. | `check_commit_ticket_staged.py` |
| `inline_work_guard` | PreToolUse | `Edit\|Write` | Blocks Edit/Write tool calls while `.build-feature.lock` exists, preventing `/build-feature` from doing implementation work before dispatching a supervisor. | `inline_work_guard.py` |
| `readme_read_guard` | PreToolUse | `Edit\|Write` | Blocks edits to gated directories (`.claude/agents/`, `.claude/skills/`, `.claude/hooks/`, `alembic/versions/`) when the nearest-ancestor README has not been read this session. | `readme_read_guard.py` |
| `documentation_guard` | PreToolUse | `Edit\|Write` | Emits a documentation-sync reminder (or blocks for L1/L2/L3 architecture docs) when a `.py` or `.sql` file is edited and a related documentation file exists in `DOC_MAPPING`. | `documentation_guard.py` |
| `check_ticket_rename_tracking` | PostToolUse | `Bash` | Verifies that a `git mv` on a ticket path is recorded as a rename (`R`) rather than separate add+delete in the staged index; attempts auto-correction if not. | `check_ticket_rename_tracking.py` |
| `readme_marker_recorder` | PostToolUse | `Read` | Records a sha256 marker when a README.md file is read, so `readme_read_guard` can verify README awareness later in the session. | `readme_marker_recorder.py` |
| `ticket_frontmatter_guard` | PostToolUse | `Edit\|Write` | Validates YAML frontmatter of any `tickets/**/*.md` file immediately after it is written; blocks with actionable feedback on missing or invalid fields. | `ticket_frontmatter_guard.py` |

---

## stdin Contract

Claude Code delivers a JSON object to each hook on **stdin** before (PreToolUse)
or after (PostToolUse) the tool executes.

### PreToolUse stdin payload

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git commit -m \"chore: update ticket\""
  },
  "session_id": "abc123"
}
```

| Field | Type | Description |
|---|---|---|
| `tool_name` | string | Name of the Claude Code tool being invoked. Common values: `Bash`, `Edit`, `Write`, `Read`. |
| `tool_input` | object | The tool's input arguments. Shape varies by tool (see below). |
| `session_id` | string | Opaque session identifier assigned by Claude Code. Present when Claude Code provides it; may be absent in some harness modes (see `CLAUDE_SESSION_ID` env var). |

#### `tool_input` shapes by tool

**Bash tool:**
```json
{
  "command": "<full shell command string>"
}
```

**Edit tool:**
```json
{
  "file_path": "/absolute/path/to/file.md",
  "old_string": "text to replace",
  "new_string": "replacement text"
}
```

**Write tool:**
```json
{
  "file_path": "/absolute/path/to/file.md",
  "content": "<full file content>"
}
```

**Read tool:**
```json
{
  "file_path": "/absolute/path/to/file.md",
  "limit": 100,
  "offset": 0
}
```
`limit` and `offset` are optional (absent = read entire file).

### PostToolUse stdin payload

The PostToolUse payload extends the PreToolUse shape with a `tool_result` field
containing the tool's output:

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "git status"
  },
  "tool_result": {
    "output": "On branch main\nnothing to commit\n",
    "exit_code": 0
  },
  "session_id": "abc123"
}
```

| Field | Type | Description |
|---|---|---|
| `tool_result` | object | Result of the tool execution. Shape is tool-specific. |
| `tool_result.output` | string | Stdout of the tool call (Bash), content returned (Read), etc. |
| `tool_result.exit_code` | integer | Exit code for Bash tool calls. |

---

## stdout Contract

### PreToolUse hooks

A PreToolUse hook controls whether the tool call proceeds by writing a JSON
decision to **stdout** and exiting.

| Outcome | stdout | Exit code | Effect |
|---|---|---|---|
| **Allow** (pass-through) | *(empty)* | 0 | Tool call executes normally. |
| **Block** | `{"decision": "block", "reason": "<message>"}` | 0 | Tool call is cancelled; Claude Code injects `<message>` back to the agent. |
| **Error / fail-open** | *(empty)* | non-zero | By convention, treated as allow. Hooks MUST catch exceptions and exit 0 to avoid blocking on unexpected errors. |

Example blocking response:
```json
{"decision": "block", "reason": "PreToolUse blocked: ticket file has unstaged modifications.\n  Ticket: tickets/00_inbox/epics/EPIC-Foo/01_ticket.md\n\nFix: git add <ticket_path> first."}
```

> **Important:** Writing `{"decision": "block", ...}` and exiting **0** (not 1)
> is the correct block pattern for PreToolUse hooks. A non-zero exit code is
> NOT used to signal a block — it is treated as a fail-open allow by Claude Code.

### PostToolUse hooks

PostToolUse hooks are **observational only** — they cannot block or cancel the
tool call that already ran.

| Outcome | stdout | Exit code | Effect |
|---|---|---|---|
| **Informational** | Any text | 0 | Output is shown to the agent as context. |
| **Auto-correction** | Status message | 0 | Hook may run corrective shell commands (e.g. `git add`) as a side-effect. |
| **Block-style feedback** | `{"decision": "block", "reason": "..."}` | 0 | Injects feedback back to Claude Code, causing the agent to self-correct (used by `ticket_frontmatter_guard`). |
| **Error** | *(any)* | non-zero | Claude Code logs a warning; the session continues. Hooks should catch exceptions and exit 0. |

---

## Exit Code Semantics

| Hook type | Exit 0 | Non-zero |
|---|---|---|
| **PreToolUse** | Allow (or block via stdout JSON decision) | Allow (fail-open — never blocks, even on error) |
| **PostToolUse** | Informational (stdout shown to agent) | Warning logged; session continues |

All hooks in this codebase are designed to **fail-open**: every `main()` function
wraps its body in a `try/except Exception` and calls `sys.exit(0)` in the except
clause. This ensures a hook crash never blocks a legitimate tool call.

---

## Timeout Guidance

Each hook entry in `settings.json` has an optional `timeout` field (seconds).

| Hook | Timeout | Notes |
|---|---|---|
| `check_commit_ticket_staged` | 10 s | Runs `git status --porcelain` — fast on any normal repo. |
| `inline_work_guard` | 10 s | File-existence check only; effectively instant. |
| `readme_read_guard` | 10 s | Walks parent dirs + reads a small JSON cache file. |
| `documentation_guard` | 5 s | Prefix matching + YAML frontmatter reads for related docs. |
| `check_ticket_rename_tracking` | 10 s | Runs `git diff --cached --name-status`. |
| `readme_marker_recorder` | 5 s | Computes sha256 of a README and writes a small JSON file. |
| `ticket_frontmatter_guard` | 5 s | Reads and parses one markdown file. |

**Recommendations:**
- Keep hook execution under **500 ms** in the common path. Claude Code injects
  hook latency into every affected tool call.
- For hooks that must do expensive work (large grep, network call), use a
  **background process** pattern: start the work asynchronously, write a marker
  file, and exit 0 immediately. A follow-up hook or pre-commit gate reads the
  marker.
- Avoid spawning sub-processes in a loop. Prefer a single `subprocess.run` call
  per hook invocation.

---

## Fail-Open Convention

Every hook MUST wrap its entire `main()` body in a `try/except Exception` block
and exit 0 on unexpected errors:

```python
def main() -> None:
    try:
        # ... hook logic ...
    except Exception:
        # Fail-open: an unexpected error must not block legitimate tool calls
        sys.exit(0)

if __name__ == "__main__":
    main()
```

**Why fail-open?** Hooks run on every matching tool call throughout the session.
A buggy hook that raises an uncaught exception and exits with a non-zero code
would appear as a silent allow (for PreToolUse) or a logged warning (for
PostToolUse) — but a hook that writes `{"decision": "block"}` erroneously
would block every tool call of that type, making the session unusable. The
fail-open pattern keeps the worst-case outcome a no-op rather than a hard block.

**Stderr for diagnostics:** When a hook exits 0 silently due to an error, print
the exception to stderr so it appears in Claude Code's debug log:
```python
except Exception as exc:
    print(f"[hook_name] unexpected error (fail-open): {exc}", file=sys.stderr)
    sys.exit(0)
```

> **Pre-commit hooks follow the same convention.** Pre-commit hooks registered
> in `commit_guardian.json` (e.g. `check-ac-schema`) apply this same fail-open
> pattern: an `if __name__ == "__main__":` block wraps `main()` in a
> `try/except Exception` and exits 0 on unexpected errors, writing a diagnostic
> prefixed with the hook name (e.g. `[check-ac-schema]`) to stderr. See
> `templates/scripts/commit_guardian/check_ac_schema.py` and
> `templates/scripts/commit_guardian/README.md` for the pre-commit hook reference.

---

## Registration Schema

Hooks are registered in `.claude/settings.json` (built from
`templates/settings.json` by `build.py`). The schema for each hook entry is:

```json
{
  "hooks": {
    "<EventType>": [
      {
        "matcher": "<tool-name-or-regex>",
        "hooks": [
          {
            "type": "command",
            "command": "<shell command to run the hook>",
            "timeout": <seconds>
          }
        ]
      }
    ]
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `<EventType>` | string | yes | `"PreToolUse"` or `"PostToolUse"`. |
| `matcher` | string | yes | Tool name or `\|`-separated list of tool names to match (e.g. `"Bash"`, `"Edit\|Write"`). Exact match against the `tool_name` field. |
| `type` | string | yes | Always `"command"` for script-based hooks. |
| `command` | string | yes | Shell command that runs the hook. The canonical pattern walks up to the repo root to resolve the hook path, so hooks work regardless of the agent's current directory. |
| `timeout` | integer | no | Maximum seconds the hook may run before being killed. Defaults to Claude Code's built-in timeout when omitted. |

### Canonical command pattern

The `templates/settings.json` uses this shell fragment to resolve the hook path
from any working directory:

```bash
bash -c 'd="$PWD"; while [ ! -d "$d/.claude/hooks" ] && [ "$d" != "/" ]; do d="$(dirname "$d")"; done; python "$d/.claude/hooks/<hook_name>.py"'
```

This walks up from `$PWD` until it finds a `.claude/hooks/` directory, then
invokes the hook script. It works correctly when an agent runs from a deep
subdirectory.

---

## Bypass / Escape Hatches

Some hooks honour environment variables to skip their checks for legitimate
exceptions:

| Hook | Env var | Effect |
|---|---|---|
| `readme_read_guard` | `CLAUDE_NO_README_CHECK=1` | Skips the README-awareness check entirely. Intended for bulk migrations where reading every README would be impractical. |
| `documentation_guard` | `CLAUDE_NO_DOC_UPDATE=1` | Skips the blocking check for arch-tagged docs. Use for trivial edits (typo fixes, comments) that do not affect architecture. Reminder still printed to stderr. |
| `inline_work_guard` | `INLINE_WORK_GUARD_MODE=warn` | Downgrades the guard from blocking (exit 2) to warn-only (exit 0 + stderr message). Useful when debugging the lock protocol without blocking edits. |

---

## Session ID and Marker Files

The `readme_read_guard` / `readme_marker_recorder` pair uses a per-session
marker file to track which README files have been read:

- **Location:** `.claude/.cache/readme_markers/<session_id>.json`
- **Format:** `{ "<absolute_readme_path>": "<sha256_hex>" }`
- **Session ID source:** `CLAUDE_SESSION_ID` env var, falling back to
  `fallback-<ppid>` when the var is absent.

**PPID mismatch caveat:** When `CLAUDE_SESSION_ID` is absent, PostToolUse
(`readme_marker_recorder`) and PreToolUse (`readme_read_guard`) hooks run in
different processes with different PPIDs, producing different `session_id`
values. The guard resolves this via an Option-B fallback scan: it checks all
`fallback-*.json` files written in the last 24 hours and accepts a match from
any of them.

---

## See Also

- [How-To: Creating a Claude Code Hook](../how-to/creating-a-claude-code-hook.md) — step-by-step guide for authoring a new hook.
- [How-To: Managing Pre-Commit Hooks](../how-to/managing-pre-commit-hooks.md) — pre-commit (git) hooks, which are distinct from Claude Code hooks.
- `templates/settings.json` — hook registration source of truth (built to `.claude/settings.json`).
- `templates/hooks/` — hook source scripts (built to `.claude/hooks/`).
