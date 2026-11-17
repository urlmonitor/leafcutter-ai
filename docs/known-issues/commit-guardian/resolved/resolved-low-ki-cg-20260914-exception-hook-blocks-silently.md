---
title: "KI-CG-20260914-exception-hook-blocks-silently — the PostToolUse exception-handling hook fails every Python write with an empty error when `ruff` is importable but not on PATH"
description: "medium. PostToolUse cannot undo the write, so no work is lost. But every `.py` Write or Edit reports a blocking hook error with no text, the check it exists to run never runs, and an agent learns to ignore the error."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-10-07'
components:
  - commit_guardian
related_docs:
  - docs/known-issues/commit-guardian.md
  - docs/known-issues/README.md
---

# KI-CG-20260914-exception-hook-blocks-silently — the PostToolUse exception-handling hook fails every Python write with an empty error when `ruff` is importable but not on PATH

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../../commit-guardian.md).
> Filename severity is the three-level index bucket (`low`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** medium. PostToolUse cannot undo the write, so no work is lost. But every `.py` Write or Edit reports a blocking hook error with no text, the check it exists to run never runs, and an agent learns to ignore the error.
- **Status:** RESOLVED 2026-10-07 — both defects fixed, in two steps on the same day. Defect 2 (the wrong stream) by `GE-108d`; defect 1 (the hook's view of ruff) by `GE-108e`, which makes the hook try `python -m ruff` before the bare executable. The entry was deliberately held open between the two; see "Partial resolution" and "Defect 1, resolved" below. The fix direction further down was written when both halves were open and is reproduced unchanged — it named both fixes correctly.
- **Occurrences:** every Python Write/Edit in one session on 2026-09-14 (dozens); reproduced again throughout 2026-10-07, where every Edit to the hook's own source — including the edits fixing it — emitted the same empty blocking error from the still-unbuilt deployed copy
- **First seen:** 2026-09-14 · **Last seen:** 2026-10-07
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

**Partial resolution, 2026-10-07 (PR #1038, `GE-108d`).** The second half of that fix direction is done and the first half is not. Both blocking `print()` calls now pass `file=sys.stderr`, and the module docstring's hook-contract line — which had documented **stdout** as the correct channel, and is the reason the code was written this way — is corrected with it. Three tests were added that run the hook as a subprocess and read the two streams separately; each refusal arm asserts stderr carries the message **and** that stdout is empty, so an implementation writing to both cannot pass. Two pre-existing tests asserting on `result.stdout` encoded the defect and were moved to `result.stderr` in the same change. Proven by mutation: red with the fix reverted, green with it applied.

**What remains open is defect 1, and it is the half that produced the original report.** `_run_ruff()` still invokes the bare `ruff` executable. On a machine where ruff is importable but has no console script on PATH — the Windows configuration this entry was first filed from — the hook still takes the `FileNotFoundError` branch and still blocks every Python write. The only change there is that the author can now *read* the install instruction instead of seeing an empty error. That is a real improvement to diagnosis and no improvement at all to the outcome: the check still never runs, and the advice it now successfully delivers ("pip install ruff") is advice the reader has already followed. Do not read the stderr fix as closing this entry.

**A note on how the remaining half will look when it bites.** Because the message now arrives, the next report of this will not be "empty blocking error" — it will be "the hook insists ruff is not installed when it is". Same defect, unrecognisable symptom.

**Defect 1, resolved 2026-10-07 (`GE-108e`).** `_run_ruff` now builds the module form —
`[sys.executable, "-m", "ruff", ...]` — and only falls back to the bare `ruff` executable
when that proves the module absent. "Is ruff installed" therefore gets the same answer
here as it does from the project's own lint step.

The disambiguation is the part worth remembering. A missing ruff **module** does not
raise: `python -m ruff` with the package absent exits non-zero and prints
`No module named ruff` to stderr. A real E722 violation also exits non-zero. So the
fallback triggers on that stderr marker, never on the exit code — treating any non-zero
exit as module-absent would send every genuine violation through a second, pointless
invocation. The `FileNotFoundError` contract is preserved: when the fallback executable
is also missing, it propagates and `main()` still emits the install instruction, now on
stderr per `GE-108d`.

Covered by three tests in `unit_tests/commit_guardian/test_exception_hook.py`, all
driving the hook as a subprocess against a real environment rather than patching the
lookup.

**Two pre-existing tests had to be corrected alongside it, and the reason is the defect
in miniature.** `test_ruff_not_found_produces_install_message` and
`test_ruff_not_found_install_message_goes_to_stderr_not_stdout` both simulated "ruff is
missing" by emptying `PATH` alone. That stopped being a simulation of absence the moment
the hook learned to look the module up — `subprocess.run([sys.executable, ...])` execs
the interpreter by absolute path and never consults `PATH`, so an importable ruff is
still found and the hook correctly passes a clean file. Both now set
`PYTHONNOUSERSITE=1` as well, which is what actually removes the module. They encoded
precisely the "not on PATH equals not installed" conflation this defect was about.

**Pattern:** a guard whose failure message is written where its host never reads it, so a blocked action and an unexplained one look identical.

---
