---
title: "Enforce commit agent delegation — block direct git commit from main agent"
status: todo
components:
  - infrastructure
  - build_pipeline
created: 2026-06-05
depends_on: []
priority: high
roadmap_phase: phase_1
advances_current_outcome: true
requires_diagram: false
requires_adr: false
ac_coverage: 0/7
files_touched:
  - templates/hooks/enforce_commit_delegation.py
  - templates/settings.json
  - templates/agents/commit.md
  - leafcutter-ai/CLAUDE.md
agents:
  architect-review: not_needed
  test-writer: needed
  python-coder: needed
  sql-coder: not_needed
  test-runner: needed
  documentation-expert: needed
  pr-reviewer: needed
  commit: needed
  pull-request: needed
  adr-author: not_needed
  architecture-diagram-author: not_needed
---

# Enforce commit agent delegation — block direct git commit from main agent

## Actor / Goal

As the leafcutter-ai package maintainer, I need the main Claude agent to be
mechanically prevented from calling `git commit` directly, so that commits are
always produced by the `commit` agent with its confirmation gate, hook-failure
handling, sign-off tracking, and background-commit safety checks — not bypassed
inline.

## Context

The main Claude agent sometimes calls `git commit` directly rather than
dispatching the `commit` agent. This bypasses the confirmation gate (Step 3 of
`commit.md`), the pre-commit hook failure → autofix path (Step 5), the sign-off
recording, the background-commit safety check, and the anomaly reporting — the
entire value of having a dedicated commit agent.

The existing `check_commit_ticket_staged.py` hook demonstrates the structural
pattern: intercept `git commit` in a `PreToolUse` Bash hook, inspect an env
var, emit a JSON block decision if the condition is not met, fail-open on errors.
This ticket adds a sibling hook using the same pattern: block `git commit` unless
`COMMIT_AGENT_MODE=1` is present in the environment (a sentinel that only the
`commit` agent template sets before its own `git commit` call).

### Affected files (implementation plan)

1. **`templates/hooks/enforce_commit_delegation.py`** — new PreToolUse hook,
   mirrors `check_commit_ticket_staged.py` in structure. Intercepts `git commit`
   Bash calls; blocks unless `COMMIT_AGENT_MODE=1` is set; fail-open on errors.

2. **`templates/settings.json`** — add the new hook to the existing PreToolUse
   Bash hook list, using the same `bash -c 'd="$PWD"; while ...'` walker pattern
   as all sibling hooks.

3. **`templates/agents/commit.md`** — prepend `COMMIT_AGENT_MODE=1 git commit`
   (or set the env var inline before the git commit call in Step 4) so the
   commit agent's own `git commit` call passes through the hook.

4. **`leafcutter-ai/CLAUDE.md`** — add an explicit instruction rule: "`git commit`
   must never be called directly. Always dispatch the `commit` agent via the
   Agent tool."

5. **`templates/hooks/enforce_commit_delegation.py`** also needs unit tests
   covering: block on missing env var, allow on env var set, fail-open on
   malformed stdin, ignore non-git-commit Bash calls.

### Why env var, not a different signal

The commit agent template runs inside a sub-agent context started by the Agent
tool. There is no reliable parent-PID chain or process-name difference. An env
var set only within the commit agent's own step is the simplest, most portable
sentinel — identical to the pattern used by `COMMIT_AGENT_MODE` in similar
enforcement hooks in other projects.

### Fail-open requirement

Like all hooks in this repo, the new hook must not block legitimate operations
when git is unavailable or the payload is malformed. Any `OSError`, JSON parse
failure, or unexpected exception exits 0 (allow). This is the established
contract for all `templates/hooks/*.py` scripts.

## Agent Contracts

### python-coder

- [ ] AC-1: Create `templates/hooks/enforce_commit_delegation.py` — a PreToolUse
  hook that reads stdin JSON, extracts `tool_input.command` (and `tool_input.cmd`
  as fallback), returns 0 silently when the command does not contain `git commit`,
  and when it does contain `git commit` returns a JSON block decision
  `{"decision": "block", "reason": "..."}` unless `os.environ.get("COMMIT_AGENT_MODE")`
  equals `"1"`. On any exception, exits 0 (fail-open). Module docstring includes
  `MODULE:`, `GOAL:`, `BUSINESS CONTEXT:`, `ARCHITECTURE:` sections and a
  `DECISION HISTORY` block with a timestamped entry.
- [ ] AC-2: Update `templates/agents/commit.md` Step 4 so that the `git commit`
  call is prefixed with `COMMIT_AGENT_MODE=1` (i.e. `COMMIT_AGENT_MODE=1 git commit -m ...`),
  making the commit agent's own commit exempt from the new hook. The existing
  heredoc form and the `2>/tmp/commit_err.txt` stderr redirect are preserved
  unchanged.
- [ ] AC-3: Update `leafcutter-ai/CLAUDE.md` with a new Shell convention rule
  under the Shell — MANDATORY section (or as a separate `## Commit Delegation —
  MANDATORY` section): "`git commit` must never be called directly. Dispatch the
  `commit` agent via the Agent tool instead."

**Delivers to test-writer:**
```
New file: templates/hooks/enforce_commit_delegation.py
  - _is_git_commit_call(payload: dict) -> bool
  - _is_commit_agent_mode() -> bool
  - main() -> None (reads stdin, prints JSON block, exits 0)
  Public interface is identical to check_commit_ticket_staged.py pattern.
  Env var: COMMIT_AGENT_MODE (string "1" = allowed)
```

**Depends on:** nothing — first phase.

### test-writer

- [ ] AC-4: Add `unit_tests/commit_guardian/test_enforce_commit_delegation.py`
  with the following test cases (pytest style, no mock.patch on builtins beyond
  `os.environ`):
  - `test_allows_non_commit_command` — payload with `command: "git status"` exits
    0 and prints nothing.
  - `test_blocks_git_commit_without_env_var` — payload with `command: "git commit -m foo"`,
    `COMMIT_AGENT_MODE` unset, asserts stdout JSON contains `"decision": "block"`.
  - `test_allows_git_commit_with_env_var` — same payload, `COMMIT_AGENT_MODE=1`
    set, asserts exits 0 and prints nothing (no block).
  - `test_fail_open_on_malformed_stdin` — empty/malformed stdin, asserts exits 0
    and no exception raised.
  - `test_fail_open_on_missing_command_key` — payload with no `command` key,
    asserts exits 0.

**Delivers to test-runner:**
```
New file: unit_tests/commit_guardian/test_enforce_commit_delegation.py
  5 test cases covering block / allow / fail-open paths.
```

**Depends on python-coder:** `templates/hooks/enforce_commit_delegation.py` must
exist before tests can import and exercise it.

### documentation-expert

- [ ] AC-5: Update `templates/settings.json` to register the new hook in the
  `hooks.PreToolUse` array under the `"matcher": "Bash"` entry, using the same
  bash walker pattern as the existing `check_commit_ticket_staged.py` entry
  (replacing `check_commit_ticket_staged.py` with `enforce_commit_delegation.py`
  in the command string). The existing hooks remain unchanged.
- [ ] AC-6: Verify (by reading) that the block message in
  `templates/hooks/enforce_commit_delegation.py` explains: (a) what was blocked,
  (b) why, and (c) the exact corrective action (`"Dispatch the commit agent via
  the Agent tool instead of calling git commit directly"`). Confirm the message
  is present and accurate; do not rewrite it — only flag if it is missing or
  misleading.

**Delivers to pr-reviewer:**
```
Updated: templates/settings.json — new PreToolUse hook entry
Verified: enforce_commit_delegation.py block message content
```

**Depends on python-coder:** `templates/hooks/enforce_commit_delegation.py`
must exist before `settings.json` can reference a real path.

### test-runner

- [ ] AC-7: Run `python -m pytest unit_tests/commit_guardian/test_enforce_commit_delegation.py -v`
  and confirm all 5 test cases pass with exit code 0. Capture and surface the
  full pytest output. Do not proceed if any test fails.

**Depends on test-writer:** test file must exist.
**Depends on python-coder:** implementation must exist.

## AC Coverage

| AC   | Test  | Implementation                                    | Validated |
|------|-------|---------------------------------------------------|-----------|
| AC-1 | AC-4  | templates/hooks/enforce_commit_delegation.py      |           |
| AC-2 | —     | templates/agents/commit.md Step 4                 |           |
| AC-3 | —     | leafcutter-ai/CLAUDE.md Shell rules               |           |
| AC-4 | AC-7  | unit_tests/commit_guardian/test_enforce_commit_delegation.py |  |
| AC-5 | —     | templates/settings.json PreToolUse hooks array    |           |
| AC-6 | —     | enforce_commit_delegation.py block message review |           |
| AC-7 | —     | pytest run result                                 |           |

## Sign-offs

- [ ] test-writer
- [ ] python-coder
- [ ] test-runner
- [ ] documentation-expert
- [ ] pr-reviewer
- [ ] commit
- [ ] pull-request

## Implementation Notes

### Hook structure (mirror of check_commit_ticket_staged.py)

```python
def _is_git_commit_call(payload: dict) -> bool:
    tool_input = payload.get("tool_input") or {}
    command = str(tool_input.get("command") or tool_input.get("cmd") or "")
    return "git commit" in command

def _is_commit_agent_mode() -> bool:
    return os.environ.get("COMMIT_AGENT_MODE", "") == "1"

def main() -> None:
    try:
        payload = json.loads(sys.stdin.read() or "{}")
    except Exception:
        sys.exit(0)  # fail-open
    if not _is_git_commit_call(payload):
        sys.exit(0)
    if _is_commit_agent_mode():
        sys.exit(0)
    print(json.dumps({"decision": "block", "reason": _build_block_message()}))
    sys.exit(0)
```

### commit.md Step 4 change

Replace:
```bash
git commit -m "$(cat <<'EOF'
```
With:
```bash
COMMIT_AGENT_MODE=1 git commit -m "$(cat <<'EOF'
```
The `2>/tmp/commit_err.txt` redirect and the heredoc close are preserved as-is.

### settings.json hook entry to add

Under `hooks.PreToolUse[matcher="Bash"].hooks`, append:
```json
{
  "type": "command",
  "command": "bash -c 'd=\"$PWD\"; while [ ! -d \"$d/.claude/hooks\" ] && [ \"$d\" != \"/\" ]; do d=\"$(dirname \"$d\")\"; done; python \"$d/.claude/hooks/enforce_commit_delegation.py\"'",
  "timeout": 10
}
```

## Out of Scope

- Updating deployed consumer copies of `settings.json` or `.claude/hooks/` —
  these regenerate on next `build-self.sh` run.
- Adding a memory entry to the user's global `.claude/memory/` directory — that
  is a human-authored step the user can do after this ticket lands.
- Blocking `git commit --amend` specifically — the hook already intercepts any
  command containing `git commit`, which includes `--amend`. This is intentional:
  amend also requires the commit agent.
- CI enforcement — the hook is a PreToolUse mechanism, not a CI check. If a
  human runs `git commit` in the terminal, it is not blocked. The CLAUDE.md rule
  is the human-facing reminder.

## Risk & Safety

- Touches money? No.
- Touches data? No — hook only inspects and blocks; no state is modified.
- Reversibility: remove the hook from `settings.json` and delete the `.py` file.
  The CLAUDE.md instruction line is a one-line revert.
- Risk of regressions: low. The hook is fail-open; any exception exits 0. The
  `COMMIT_AGENT_MODE=1` prefix on the commit agent's `git commit` call is an
  env-var prefix, which `bash` supports natively and does not change git's
  behavior. The existing `check_commit_ticket_staged.py` hook continues to
  run independently.
- Pre-existing passing tests: updating `commit.md` Step 4 does not affect any
  existing unit tests (the commit agent template is not imported by tests).

## Comments
