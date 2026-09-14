---
title: "KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace"
description: "KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace"
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-08-18'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** open
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js:1740` → `scripts/setup_ticket_worktree.py` `_git_toplevel()`

**Symptom.** `/plan-feature` dies before triage, before the product-truth phase, and
before any authoring agent runs. It returns
`status: error — Authoring worktree creation failed (exit code 1)` with a
`subprocess.CalledProcessError` from `git rev-parse --show-toplevel`. Nothing is
authored and nothing is written.

**Root cause — two layers, both needed to reproduce.**

1. The workflow shells a **relative** path:
   `python .leafcutter/scripts/setup_ticket_worktree.py create-ac-worktree`, dispatched
   through a `status-checker` agent. Which copy of the script runs therefore depends on
   the caller's working directory. In the ADR-001 self-hosting dev layout the session
   cwd is the workspace parent (`leafcutter/`), so it selects
   `<workspace>/.leafcutter/scripts/` — the deployed build output.

2. `_git_toplevel()` defaults its anchor to `Path(__file__).resolve().parent`. That
   directory is `<workspace>/.leafcutter/scripts/`, and `<workspace>` is **untracked** —
   `leafcutter-ai/` is the git root, one level *down*. So `rev-parse` exits 128.

The function's own docstring names this exact layout as the thing it is protecting
against — *"the leafcutter dev layout where `leafcutter-ai/` is the git root but the
script may be launched from its parent"* — and then defeats that intent one line later
by asserting *"the script always lives physically inside the repository it operates
on."* Under self-hosting the deployed copy does not.

**Evidence.** Reproduced directly:

```
$ git -C /home/henzeh/projects/leafcutter/.leafcutter/scripts rev-parse --show-toplevel
fatal: not a git repository (or any of the parent directories): .git
exit: 128
```

The same command against any worktree-local copy succeeds and returns that worktree's
root. Full traceback in the failed run's workflow result (`run_id: scanner-hardening-1`).

**Why it is not caught by tests.** Unit tests for `setup_ticket_worktree.py` invoke it
from a `tmp_path` fixture that *is* a git repository, so the default anchor always
resolves. The failure needs the real deployed layout — a copy of the script sitting in
an untracked parent — which no fixture reproduces. Same class as the
`check_secrets` root-resolution defect fixed in GE-118a-1.

**Fix direction.** Two candidates, not mutually exclusive:

- Make `_git_toplevel()` honest about the layout it documents: on failure of the
  script-dir anchor, fall back to locating the repository rather than raising. A
  conservative rule that works: probe the immediate children of the workspace for git
  toplevels and accept the result only when exactly one is found; otherwise re-raise.
- Better, in `plan-feature.js`: stop invoking a cwd-relative `.leafcutter/` path.
  Resolve the script from the repository the workflow is operating on, so the copy that
  runs is never a function of where the session happens to be sitting.

Whichever lands must be covered by a test that executes the script from a directory
that is **not** a git repository, with the script itself outside the repo — otherwise
the fixture bias that hid this recurs.

**Workaround used 2026-08-18.** Patched the *deployed* copy at
`<workspace>/.leafcutter/scripts/setup_ticket_worktree.py` with the single-candidate
fallback above, warning on stderr when it fires. This is **build output** — `build.py`
overwrites it from `templates/`, so the workaround evaporates on the next build and is
not a fix.

---
