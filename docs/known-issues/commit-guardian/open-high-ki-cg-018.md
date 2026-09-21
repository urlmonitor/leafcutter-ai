---
title: "KI-CG-018 — `check_ac_governance` exits 0 without inspecting anything, and its own \"did I look?\" diagnostic cannot fire on the paths where it did not"
description: "KI-CG-018 — `check_ac_governance` exits 0 without inspecting anything, and its own \"did I look?\" diagnostic cannot fire on the paths where it did not"
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

# KI-CG-018 — `check_ac_governance` exits 0 without inspecting anything, and its own "did I look?" diagnostic cannot fire on the paths where it did not

> One known issue, split out of `docs/known-issues/commit-guardian.md` on
> 2026-09-14. Index: [commit-guardian.md](../commit-guardian.md).
> Filename severity is the three-level index bucket (`high`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** high
- **Status:** open
- **Occurrences:** 2
- **First seen:** 2026-08-25 · **Last seen:** 2026-08-25
- **Where:** `templates/scripts/commit_guardian/check_ac_governance.py:631-642` — `main()`

**Symptom.** The hook returns `0` having read no file, with no output on stdout or stderr,
and is indistinguishable at the call site from a run that checked every staged record and
found nothing wrong.

**Root cause — the diagnostic is downstream of the silent exits.** `main()` has two early
returns, and the introspection counter that exists to prove the hook did work sits *after*
both of them:

```python
631    if not ac_store.is_dir():
632        # No AC store — exit 0 immediately without creating any directories
633        return 0
634
635    # Get staged AC YAML files
636    staged_paths = _get_staged_ac_paths()
637    if not staged_paths:
638        return 0  # No AC files staged — nothing to check
639
640    # Emit parsed file count to stderr for test introspection (AC-13)
641    if os.environ.get("HOOK_COUNT_PARSED"):
642        print(f"{_HOOK_PREFIX} parsed_files: {len(staged_paths)}", file=sys.stderr)
```

`HOOK_COUNT_PARSED` was added so a caller could confirm the hook saw its files. It is
unreachable on precisely the two paths where it saw none. Setting it and getting silence is
therefore ambiguous between "the variable is unset", "the hook is old", and "the hook
checked nothing" — and only the third is true.

Line 631 is reached with `ac_store` wrong whenever `_find_project_root()` resolves above the
AC store. In the ADR-001 self-hosting layout the workspace parent carries a `CLAUDE.md` but
no `docs/acceptance-criteria/`, so a run whose working directory is the workspace parent
takes the 633 exit every time. Not intermittent.

**Evidence.** Both observed on 2026-08-25 while authoring `ACD-2100`, by two agents
independently, on a worktree that did contain 31 staged AC records:

```
$ HOOK_COUNT_PARSED=1 HOOK_TEST_FILES=<relative path to a real staged AC> \
    python <worktree>/.leafcutter/scripts/commit_guardian/check_ac_governance.py
(no output at all)
exit: 0

$ env --chdir=<worktree> HOOK_COUNT_PARSED=1 HOOK_TEST_FILES=<same path> \
    python <worktree>/.leafcutter/scripts/commit_guardian/check_ac_governance.py
[check-ac-governance] parsed_files: 1
exit: 0
```

Same hook, same file, same exit code; only the working directory differs, and only the
second run inspected anything.

**Compounding: `argv` is ignored.** `_get_staged_ac_paths()` (`:285`) reads `git diff
--cached` or `HOOK_TEST_FILES`. Passing paths on the command line does not make the hook
check them, so a caller who verifies the hook by invoking it with a path gets a pass that
means nothing. This is the same shape already recorded for the other AC hooks — silence is
not a pass, and neither is exit 0 with an argument the hook never read.

**Why this is worse than a crash.** In pre-commit the working directory is the repository
root, so the gate does run there — its practical blast radius is ad-hoc verification, agent
self-checks, and any CI step that invokes it from elsewhere. Those are exactly the callers
who would report "governance passes" on the strength of an exit code.

**Fix direction.** Three separable changes, in order of value:

- Emit the `HOOK_COUNT_PARSED` diagnostic (or an unconditional one-line summary naming the
  resolved root and the file count) **before** the early returns, so a run that checked
  nothing says so. A check that cannot report what it looked at should not be able to
  report success.
- Distinguish "no AC store found at `<resolved root>`" from "AC store found, nothing
  staged". Both are legitimately exit 0; they are not the same fact.
- Resolve the root the way the guardian hooks that already handle this layout do —
  `_resolve_root.py` exists for it. Falling back to a bare relative `_AC_STORE_DIR` when
  `_find_project_root()` returns `None` (`:627`) is what makes the failure depend on cwd.

**Pattern:** `docs/reference/false-green-mechanisms.md` → M8, and a variant worth naming
separately: the *instrumentation* meant to defeat M8 placed where the M8 path cannot reach
it.

---
