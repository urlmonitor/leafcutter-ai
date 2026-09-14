---
title: "KI-CG-20260914-contract-guard-crashes-on-diff-bytes — the contract-shrinking guard decodes the staged diff in the console code page, crashes on the first non-cp1252 byte, and blocks the commit instead of failing open"
description: "high on Windows. Any commit whose staged diff contains a byte that cp1252 cannot decode is refused, and no content change fixes it. In practice that means most large merges, and any diff touching UTF-8 text such as `…`, `—` or `✓`. The fail"
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

# KI-CG-20260914-contract-guard-crashes-on-diff-bytes — the contract-shrinking guard decodes the staged diff in the console code page, crashes on the first non-cp1252 byte, and blocks the commit instead of failing open

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high on Windows. Any commit whose staged diff contains a byte that cp1252 cannot decode is refused, and no content change fixes it. In practice that means most large merges, and any diff touching UTF-8 text such as `…`, `—` or `✓`. The failure also contradicts the guard's own documented disposition: a could-not-check outcome should fail open and announce itself (GE-120a-1).
- **Status:** open
- **Occurrences:** 1 (2026-09-14: concluding a merge of `origin/main` into `feature/uxp-700-tranche-2`, 104 staged paths)
- **First seen:** 2026-09-14 · **Last seen:** 2026-09-14
- **Where:** `templates/scripts/commit_guardian/check_contract_shrinking.py`. Its `subprocess.run(..., capture_output=True, text=True, ...)` calls (around lines 274, 311 and 352) set no `encoding`. `main()` (around line 528) then calls `diff.strip()` on the result without a guard.

**Symptom.**

```text
Check Contract Shrinking (TDD Guard).......Failed
Exception in thread Thread-1 (_readerthread):
  File "C:\Python314\Lib\subprocess.py", line 1613, in _readerthread
    buffer.append(fh.read())
UnicodeDecodeError: 'charmap' codec can't decode byte 0x90 in position 275132: character maps to <undefined>
  File "...\check_contract_shrinking.py", line 529, in main
    if not diff.strip():
AttributeError: 'NoneType' object has no attribute 'strip'
```

Setting `PYTHONIOENCODING=utf-8` on the outer `git commit` reproduced the crash unchanged. That variable governs Python's standard streams, not the decoding `subprocess` applies to a child's pipe, which with `text=True` and no `encoding` is `locale.getpreferredencoding()`, i.e. cp1252.

**Mechanism.** Two defects stack.
1. **Wrong encoding.** Git emits the diff as UTF-8 bytes, and the guard decodes them as cp1252. Byte `0x90` is undefined in cp1252, and it occurs inside UTF-8 sequences such as `…` (`E2 80 A6`) or `—` (`E2 80 94`). The decode fails in `subprocess`'s reader thread, and that exception is printed rather than raised, so `proc.stdout` comes back `None` instead of the exception reaching the caller.
2. **No guard on the result.** `main()` treats the diff as a string unconditionally. The `None` becomes an `AttributeError`, exit 1, and a refused commit. The guard's "could not check" path is never reached, so the crash reads as a verdict.

A small diff rarely contains such a byte; a merge of several PRs almost always does. The guard therefore works for everyday commits and fails exactly when a branch is brought up to date.

**Workaround in use.** The branch's single real commit was replayed onto a fresh branch from `origin/main` (`git cherry-pick --no-commit`), and the generated `docs/INDEX.md` was regenerated. The guard then ran over that commit's own small diff, not the whole merge. Every hook still ran.

**Fix direction.**
- Pass `encoding="utf-8", errors="replace"` to every `subprocess.run` in the guard, or read bytes and decode explicitly.
- Treat a `None` or undecodable diff as the could-not-check outcome: announce it, and do not block.
- Add a test that stages a file containing `…` and runs the guard as a subprocess with `PYTHONIOENCODING` removed from its environment. It must assert a verdict rather than a traceback.
- Grep the other commit-guardian scripts for `text=True` without `encoding`: the same pattern is likely elsewhere.

**Related.** `KI-BP-20260914-build-crashes-on-a-cp1252-stdout` (`build-pipeline.md`) is the output-side twin of this input-side defect, found the same day. Both come from implicit locale encoding on Windows, which Linux CI can never exercise.

**Pattern:** a guard whose crash path and whose blocking path share an exit code, so a tool failure is indistinguishable from a finding.
