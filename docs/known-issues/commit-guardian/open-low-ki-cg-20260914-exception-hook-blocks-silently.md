---
title: "KI-CG-20260914-exception-hook-blocks-silently — the PostToolUse exception-handling hook fails every Python write with an empty error when `ruff` is importable but not on PATH"
description: "medium. PostToolUse cannot undo the write, so no work is lost. But every `.py` Write or Edit reports a blocking hook error with no text, the check it exists to run never runs, and an agent learns to ignore the error."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-exception-hook-blocks-silently — the PostToolUse exception-handling hook fails every Python write with an empty error when `ruff` is importable but not on PATH

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. PostToolUse cannot undo the write, so no work is lost. But every `.py` Write or Edit reports a blocking hook error with no text, the check it exists to run never runs, and an agent learns to ignore the error.
- **Status:** open
- **Occurrences:** every Python Write/Edit in one session on 2026-09-14 (dozens)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `.claude/hooks/check_exception_handling_hook.py`, in `_run_ruff()` (which invokes the bare `ruff` executable) and in `main()`'s `FileNotFoundError` branch (which `print()`s to stdout and then `sys.exit(2)`)

**Symptom.** After each Python file write, the harness shows:

```text
PostToolUse:Write hook blocking error from command: "bash -c '... python "$d/.claude/hooks/check_exception_handling_hook.py"'": No stderr output
```

**Reproduction.** On this Windows machine, `ruff` is installed as a module but has no console script on PATH:

```text
$ which ruff                 -> no ruff in (...)
$ python -m ruff --version   -> ruff 0.15.15
$ python -c "import json,subprocess,sys; p=r'<abs path to any .py>'; r=subprocess.run([sys.executable,'.claude/hooks/check_exception_handling_hook.py'],input=json.dumps({'tool_name':'Write','tool_input':{'file_path':p}}),capture_output=True,text=True); print(r.returncode, len(r.stderr)); print(r.stdout[:60])"
2 0
EXCEPTION HANDLING HOOK: ruff not found on PATH.
```

**Mechanism.** There are two defects, and either would have been survivable alone.
1. **The hook's view of ruff.** It asks the OS for a `ruff` binary, but the project's own lint step (`python -m ruff check ...`) and every other hook reach ruff as a module. "Is ruff installed" gets a different answer here than everywhere else.
2. **The wrong stream.** The hook writes its explanation, including the install instructions, to **stdout** and exits 2. For exit code 2, Claude Code surfaces **stderr** to the model. The message that would have explained the block is discarded, and what remains reads "No stderr output". The reader cannot tell a missing tool from a lint violation from a crash.

**Fix direction.** Run ruff as `[sys.executable, "-m", "ruff", ...]`, falling back to the bare binary only if the module is absent. Send every blocking message (`_build_block_message` and `_build_ruff_not_found_message`) to `sys.stderr`. Add a test that runs the hook as a subprocess with ruff unavailable and asserts the exit code is non-zero *and* the stderr text names the missing tool. The test must not assert on stdout.

**Pattern:** a guard whose failure message is written where its host never reads it, so a blocked action and an unexplained one look identical.

---
