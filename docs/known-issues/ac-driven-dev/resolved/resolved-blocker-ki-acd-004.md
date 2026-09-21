---
title: "KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace"
description: "KI-ACD-004 — RESOLVED 2026-09-14: `/plan-feature` could not start in the self-hosting layout because worktree setup resolved git from the untracked workspace; all five ACD-2100a records have landed on repository-anchored resolution."
type: reference
category: reference
status: active
created: '2026-08-18'
last_updated: '2026-09-14'
components:
  - ac_driven_dev
related_docs:
  - docs/known-issues/ac-driven-dev.md
  - docs/known-issues/README.md
---

# KI-ACD-004 — `/plan-feature` cannot start in the self-hosting layout: worktree setup resolves git from the untracked workspace

> One known issue, split out of `docs/known-issues/ac-driven-dev.md` on
> 2026-09-14. Index: [ac-driven-dev.md](../../ac-driven-dev.md).
> Filename severity is the three-level index bucket (`blocker`); the
> original grading is the `**Severity:**` line below, unchanged.

- **Severity:** blocker
- **Status:** fixed (2026-09-14 — closes now that `ACD-2100a-3` and `ACD-2100a-4`, the two
  sibling sites tracked separately since the 2026-08-31 partial fix, have themselves landed
  on repository-anchored resolution; see "Fix landed" below for both dates). All five records
  in this family (`ACD-2100a-1` through `-5`) are `work_status: done`.
- **Occurrences:** 1
- **First seen:** 2026-08-18 · **Last seen:** 2026-08-18
- **Where:** `templates/workflows-js/plan-feature.js:1740` → `scripts/setup_ticket_worktree.py`
  `_git_toplevel()` / `_resolve_repository_with_search_fallback()`

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

**Fix landed 2026-08-31 (`ACD-2100a-1`).** Took the second "Fix direction" candidate,
in `templates/workflows-js/plan-feature.js` (the source template — not the deployed
`.leafcutter/` copy per ADR-001's self-hosting boundary):

- `buildRepoAnchoredResolutionCommand(relPath)` builds a single-line POSIX-sh command
  that resolves `.leafcutter/<relPath>` to an absolute path anchored at the actual git
  repository — `git rev-parse --show-toplevel` first, falling back to probing the
  session cwd's immediate child directories for exactly one git toplevel when that
  fails (the self-hosting layout this issue's root cause names). It never falls back to
  a cwd-relative guess: an unresolved repository or a resolved-but-missing file both
  exit non-zero with a diagnostic naming the location that could not be found.
- `resolveRepoAnchoredScriptPath(relPath, agentType, label)` dispatches that command to
  a `status-checker` agent and fails closed — any dispatch error, non-zero exit, or
  unparseable output is returned as `{ ok: false, message }`, never silently swallowed
  into a fallback, per this repository's error-handling policy for external I/O.
- The worktree-setup dispatch (`create-ac-worktree`) resolves `scripts/setup_ticket_worktree.py`
  through this mechanism *before* building its own command text, and embeds the
  resolved absolute path literally into that command — so the run's own record of the
  command it issued names the absolute, repository-anchored location, not a
  `{{config.output_root}}`-relative one. On resolution failure, the same diagnostic is
  re-issued under the `worktree-setup` step's own label rather than a separate early
  return, so a wrong-copy failure is observable on that step's own record.
- Covered by `unit_tests/workflows/test_acd_2100a_1.py` (a real, on-disk two-copy
  reproduction driven from an untracked, non-repository cwd — not a mock-only test).

**Fix landed 2026-08-31 (`ACD-2100a-2`), as defense-in-depth inside the script itself.**
Independent of the caller-side fix above, `_git_toplevel()`'s own anchor-based resolution
in `scripts/setup_ticket_worktree.py` now falls back to a bounded search when the anchor
fails — implementing the first "Fix direction" candidate above (the second is what
`ACD-2100a-1` took), so the script recovers on its own even when a caller other than the
now-fixed `plan-feature.js` invokes it from an unexpected `cwd`:

- `_search_immediate_subdirectory_repos()` probes the *immediate* subdirectories of the
  process's current working directory for git toplevels — never walking upward past the
  starting directory, never following a symlinked child out of it, and rejecting a
  candidate whose own `git rev-parse --show-toplevel` resolves to some ancestor rather
  than the candidate itself.
- `_resolve_repository_with_search_fallback()` keeps the anchor as the first choice,
  unchanged for every caller that already works; the bounded search runs only when the
  anchor raises, and only a single unambiguous candidate is accepted — zero or multiple
  candidates raise rather than guessing.
- A search-based resolution always announces itself on stderr at WARNING level, naming
  the selected repository and stating that the selection came from a search rather than
  the script's own location — silence here would be indistinguishable from the anchor
  having worked and would leave a future wrong-repository incident undiagnosable.
- An explicit `--repo-root` flag on the `create-only` subcommand bypasses both the anchor
  and the search outright, so callers with a known-good location are unaffected.
- Covered by `unit_tests/ac_driven_dev/test_acd_2100a_2.py` — real-subprocess integration
  tests driven from a genuinely non-repository directory with exactly one git repository
  among its immediate subdirectories, exercising the script's actual command-line entry
  point rather than importing the resolver.

**Known related gap, left open by design.** `_create_ac_worktree()` and
`_create_fastlane_worktree()` share the same anchor-only `_git_toplevel()` call (and the
same historical stdout-pollution pattern on `git worktree add`, also fixed for
`create-only` in this pass) but were not brought onto this fallback — they are outside
`ACD-2100a-2`'s AC/test scope. Track as a future ticket rather than treating the
worktree-setup site as fully hardened across all three subcommands. **This gap does not
reopen this entry:** it was deliberately scoped out, it is a different pair of
subcommands from the one this entry's symptom names, and the two sites it covers are not
on `/plan-feature`'s startup path.

This is explicitly a **shared** mechanism, not a per-site patch: `buildRepoAnchoredResolutionCommand`
/ `resolveRepoAnchoredScriptPath` are written for reuse by the sibling
`{{config.output_root}}`-relative sites named in the "Fix direction" above — the AC
registry read (`ACD-2100a-3`) and the pause-store read/write (`ACD-2100a-4`). Those two
sites had not yet been migrated onto this mechanism as of the 2026-08-31 fix and remained
open until the 2026-09-14 pass recorded below; a per-site fix alone is exactly what left
three sites standing after this class of defect was first filed. See
[`docs/architecture/components/ac-driven-dev.md`](../../../architecture/components/ac-driven-dev.md)
and
[`docs/architecture/components/worktree-manager.md`](../../../architecture/components/worktree-manager.md)
for the components this resolution site touches, and
[ADR-001](../../../architecture/adrs/ADR-001-self-hosting-boundary.md) for the
self-hosting layout this fix resolves against. The standing reference page for
`/plan-feature`'s layout and startup-time resolution checks now exists at
[`docs/reference/plan-feature-layout-and-startup-checks.md`](../../../reference/plan-feature-layout-and-startup-checks.md);
cross-link from there back to this entry rather than duplicating this narrative.

**Fix landed 2026-09-14 (`ACD-2100a-3`, `ACD-2100a-4`).** The two sibling sites this
entry tracked as open above have themselves now landed on repository-anchored
resolution, verified directly against the current code rather than taken on the
epic's own say-so:

- `ACD-2100a-3` ("the startup charter check finds the agent registry when the run
  starts inside a worktree") is implemented in
  `scripts/worktree/check_workspace_setup_permission.py`'s `resolve_repo_root()`,
  which reads `git rev-parse --git-common-dir` (the form that resolves correctly for
  a linked worktree, whose `.git` is a file rather than a directory) with a bounded
  child-directory probe as fallback — independent of, but the same shape as,
  `ACD-2100a-1`'s `buildRepoAnchoredResolutionCommand()`. Covered by
  `unit_tests/workflows/test_acd_2100a_3.py`.
- `ACD-2100a-4` ("a pause record written from inside a worktree is found again by the
  run that resumes") is implemented via `buildPauseStoreCommand()`'s
  `_buildRepoRootResolutionSnippet()` in `templates/workflows-js/plan-feature.js` — the
  same repo-anchoring primitive `ACD-2100a-1` established, applied to the pause-store
  read/write. Covered by `unit_tests/workflows/test_acd_2100a_4.py`, including a real
  round-trip test that writes a pause record from inside a worktree fixture and reads
  it back from a second process started at the project root.
- `ACD-2100a-5` ("a run reaches its first question to the user from any working
  directory") is the direct end-to-end regression test for this entry's original
  symptom: it drives the same run from the project root, a worktree, and a directory
  containing neither the project nor any installed support files, and asserts all
  three reach the same first user-facing question with no run halting on an
  unresolved file. Covered by `unit_tests/workflows/test_acd_2100a_5.py`.

**Evidence, re-run for this entry on 2026-09-14.**
`python -m pytest unit_tests/workflows/test_acd_2100a_1.py unit_tests/workflows/test_acd_2100a_3.py unit_tests/workflows/test_acd_2100a_4.py unit_tests/workflows/test_acd_2100a_5.py`
→ 13 passed; `unit_tests/ac_driven_dev/test_acd_2100a_2.py` → 4 passed. The four
`-1/-3/-4/-5` files were RED for the whole epic until today's `d4146f162` ("supply
args-shaped pre-flight verdict in 17 tests"): `ACD-2100b-5` (landed 2026-09-07) changed
how the Pre-Stage-0 workspace-setup permission verdict reaches the workflow —
`args.workspace_setup_permission` instead of an agent-dispatch label — and these four
files still supplied the old label-shaped stub, so every one of them failed closed at
Stage 0 before ever reaching the behaviour under test. `d4146f162` added each file's own
`_real_preflight_verdict()` helper, which runs the real on-disk pre-flight script and
uses its actual output. The fix this entry describes finally has passing evidence
behind it, rather than a green-looking gate that never exercised the code.

---
