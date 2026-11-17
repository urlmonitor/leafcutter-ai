---
title: "KI-KM-20261008-harvest-state-default-is-cwd-relative — the harvester's --state default is relative to the working directory, so a run that omits the flag drops a file into the package root that makes build.py's closure guard abort every later build"
description: "high (latent) — scripts/knowledge/harvest_cli.py defaults --state to Path(\"debugging/logs/harvest_state.json\"), relative to the process's working directory. If an ordinary harvester run routes at least one event without --state from the package root, it writes that file under the root. The BP-900g-8 closure guard treats a path literal in a deployed script as a dependency once the file exists under the root, so every later build.py run aborts with [CLOSURE GUARD] UNDEPLOYED DEPENDENCY. Reproduced on main fbf0c522 on 2026-10-08. PR #877 hit the same trap with --marker (fixed in merge 3f31757f); --state has the same problem but nothing has triggered it yet. No test on main triggers it today. The three workflow knowledge-routing steps and the knowledge-harvester agent do."
type: reference
category: reference
status: active
created: '2026-10-08'
last_updated: '2026-10-08'
components:
  - knowledge_management
  - build_pipeline
related_docs:
  - docs/known-issues/knowledge-management.md
  - docs/known-issues/README.md
  - docs/known-issues/build-pipeline/open-low-ki-bp-20260928-closure-guard-reads-comparison-literals-as-file-reads.md
---

# KI-KM-20261008-harvest-state-default-is-cwd-relative — the harvester's `--state` default depends on the working directory, and a stray state file makes every later build abort

> **Why this register.** Filed in `knowledge-management` because the defect and the fix are
> both in the harvester (`scripts/knowledge/harvest_cli.py`). It is a default that depends on
> the working directory. The build-pipeline closure guard is only where it shows up, and that
> guard is doing what it was designed to do. The harvester's earlier defect, `KI-KM-011`, is
> filed here for the same reason. `components:` names `build_pipeline` too, so someone
> searching from the build side can find it. Index: [knowledge-management.md](../knowledge-management.md).

- **Severity:** high. It is latent: no test on main triggers it today. When it does fire, it
  breaks every later `build.py` run in that tree. In CI that means over a hundred failures, and
  the error that explains them is truncated off-screen (see "Why it hides"). The bucket takes
  the worse of the two readings.
- **Status:** open, no AC.
- **Occurrences:** 1, the same mechanism through the sibling `--marker` flag in PR #877. CI
  showed about 124 failed tests and 44 errors that never reproduced locally. `--state` itself
  has not fired yet.
- **First seen:** 2026-10-08, while landing PR #877 · **Last seen:** 2026-10-08
- **Where:** `scripts/knowledge/harvest_cli.py:82-88`:

  ```python
  parser.add_argument(
      "--state",
      type=Path,
      default=Path("debugging/logs/harvest_state.json"),
  ```

  It is written by `_save_state` (`scripts/knowledge/harvest_learnings.py:291`, called at
  `:822`). The guard that turns the stray file into a failed build is in
  `scripts/build_referential_integrity.py` (docstring at `:513`: "non-existence under *root*
  is itself the discriminator"). `build.py` reports it as `[CLOSURE GUARD]` (AC BP-900g-8).

## Symptom

`build.py --target-dir <anything>` exits 1 with:

```text
[CLOSURE GUARD] UNDEPLOYED DEPENDENCY: deployed script 'scripts/knowledge/harvest_cli.py' resolves 'debugging/logs/harvest_state.json' (via import, relative path, or dynamic loader), but no deploy phase ships it. It belongs in the 'build_workflow_tools or build_template_standalone_scripts' phase's deploy declaration (scripts/build_phases.py).
[CLOSURE GUARD] Build aborted: every intra-package dependency a deployed script resolves must itself be deployed (AC BP-900g-8).
```

Every test that spawns `build.py` then fails. The source tree has not changed in any way
`git status` can show.

## Reproduction (run 2026-10-08 against origin/main `fbf0c5223`)

In a scratch detached worktree of origin/main, with no other change:

1. Create `<scratch>/debugging/logs/harvest_state.json` (content `{}`; only existence matters).
2. `python3 <scratch>/scripts/build.py --target-dir <test-logs>/ki-state-repro-with-file`
   gave **exit 1** and the two `[CLOSURE GUARD]` lines above, word for word, naming
   `debugging/logs/harvest_state.json`.
3. Remove the file.
4. `python3 <scratch>/scripts/build.py --target-dir <test-logs>/ki-state-repro-without-file`
   gave **exit 0** with no `[CLOSURE GUARD]` lines.

The state file's existence alone decides whether the build passes.

## Root cause

Two behaviours combine, and each makes sense by itself:

1. **The harvester's default depends on the working directory.**
   `Path("debugging/logs/harvest_state.json")` resolves against the process's working
   directory, not the package or the deployed output root. Any ordinary run without `--state`
   writes to `<cwd>/debugging/logs/harvest_state.json`. Under pytest, and for an agent told to
   "run from the repository root", that working directory is the checkout.
2. **The closure guard decides by whether the file exists.** It treats a `dir/file.ext`
   literal in a deployed script as a data dependency **if the file exists under the package
   root**. That is how it finds real reads without an allow-list. When the file is absent,
   the literal is ignored. When a stray file is present, the same literal becomes an
   undeployed dependency, so the guard aborts.

So whether the build passes depends on what some earlier process happened to leave in the
checkout.

**The write is conditional, which makes it harder to pin down.** `harvest()` persists state only
when `not dry_run and new_hashes`, meaning at least one event was routed. A run over an empty or
all-unroutable sink writes nothing. `--dry-run`, `--status` and `--print-sink` never write
state; the last two return in `main()` before `harvest()` is called. A run that omits
`--state` is therefore harmless until the day it routes something.

## Why it never reproduces locally

It depends on **test order** and on **what the tree already holds**. A fresh clone, a single
test file, or a `-k` selection has no stray file, so `build.py` passes. In a full pytest
session the build-spawning tests only fail if they run *after* something has written the file
into the checkout. The order differs between local runs, CI shards and reruns, so the same
commit can be green locally and broadly red in CI. #877 showed exactly this.

## Why it hides

- **The file is gitignored** (`.gitignore:60`, `debugging/logs/`). `git status` stays clean, so
  nothing shows that the tree differs from a fresh clone.
- **Test assertions truncate `build.py`'s stdout.** The tests that spawn the build print a
  shortened copy of its output in the failure message, and the `[CLOSURE GUARD]` line was cut
  off. On #877 this led to two wrong diagnoses before anyone read the full build output.
- **The failure appears far from the cause.** The tests that fail are build tests, not
  harvester tests, and the one that wrote the file passed.

## Precedent: `--marker` in PR #877

PR #877 (INF-700a-2) added `--marker` with the default
`Path("debugging/logs/harvest_last_run.json")`, also relative to the working directory. That
produced about 124 failed tests and 44 errors in CI, with the cause described above.
Fix commit `867242c77` ("derive harvest --marker default from --state, not cwd"), merged in
**`3f31757f`**, changed the default to `None` and resolves it after parsing as
`args.state.parent / "harvest_last_run.json"`. The marker now sits next to the state file, and
the only literal left in the source is the bare name `harvest_last_run.json`. The guard does
not treat a bare name as a dependency because it has no directory part.

That fix covers `--marker` only when the caller supplies `--state`. If `--state` is left at
its default, the marker lands next to it in `<cwd>/debugging/logs/`. The guard will not fire
on the marker, but the file still lands in the checkout. The comment above `_MARKER_NAME` in
`harvest_cli.py` ("a test run from the repo root no longer drops a marker into the checkout")
is true only when `--state` is passed.

## Live triggers on main (`fbf0c5223`)

**Tests: none today.** Every harvester invocation in `tests/` and `unit_tests/` was checked.
None runs an ordinary harvest without `--state` from the checkout. These are the near misses,
any of which becomes a live trigger if changed slightly:

- `tests/knowledge/_inf_400c_4_helpers.py::_run_harvester_default` (used by
  `tests/knowledge/test_inf_400c_4_seams.py`) and
  `unit_tests/portability/test_inf_400c_4_v.py::_run_harvester_default` both omit `--state`.
  They are safe only because each sets `cwd=` to a `tmp_path` directory. Remove that `cwd=`,
  or point it at the repo, and they become triggers.
- `unit_tests/workflows/test_inf_700a_2.py::_run_status` and
  `tests/knowledge/test_inf_700a_2.py::_run_status` omit `--state` and run with no `cwd`
  (so in the checkout). They are safe only because `--status` returns before `harvest()`.
- `tests/knowledge/test_inf_400c_5.py::_run_harvester` passes no `cwd`. It is safe only because
  its one caller passes `--state`. A second caller that leaves `--state` out would be a trigger.

**Outside tests: four live invocation sites.** Each runs an ordinary harvest without `--state`
from the repository root:

- The knowledge-routing step in `templates/workflows-js/build-epic.js:558`,
  `templates/workflows-js/fast-lane-ship.js:1721` and `templates/workflows-js/quick-fix.js:915`,
  each `python3 {{config.output_root}}/scripts/knowledge/harvest_learnings.py` with the
  instruction "Run this single Bash command from the repository root".
- `templates/agents/knowledge-harvester.md:120` and `:132` (`--verbose`, and `--sink ...`).
  `:126` is `--dry-run` and never writes state.

In a consumer project the repository root is the consumer's root, not the package root, so the
guard does not see the file. **In this repo it does.** A `leafcutter-ai` worktree's root *is*
the package root, so one of these steps routing a single event there leaves the tree unable to
build until someone finds and deletes a gitignored file.

## Fix direction

1. **Anchor the default to a fixed directory.** Resolve `--state` after parsing, as `--marker`
   now is, against `_sink_resolution.deployed_output_root()` (already computed in `main()`),
   e.g. `<output_root>/debugging/logs/harvest_state.json`. Then no run writes into the working
   directory. Keep the directory-qualified literal out of the source: build it from parts, or
   default to `None` and fill it in after parsing, so the closure guard has nothing to match.
2. **Make tests always pass a temporary `--state`.** Pass `tmp_path / "state.json"` in every
   test helper that runs the harvester, including `--status`/`--print-sink` helpers, so a
   later edit cannot quietly turn them into triggers. A small regression test is worth having:
   run the harvester from a temporary working directory with one routable event and no
   `--state`, then assert nothing was written under that directory.
3. **Optional, on the build side:** have the build-spawning test helpers print the
   `[CLOSURE GUARD]` lines (or the full stdout) when an assertion fails, so this class of
   failure can be read straight from the CI log. That would have saved the two wrong
   diagnoses on #877.

Until then, the workaround is to delete `debugging/logs/harvest_state.json` (and
`harvest_last_run.json`) from the package root and rebuild.

**Related.** `KI-BP-20260928-closure-guard-reads-comparison-literals-as-file-reads` is the same
guard flagging a path literal that does not need deploying. That one fails on every build; this
one fails only when a stray file is present.

**Pattern:** a deployed script with a default path relative to the working directory means any
test that forgets the flag can write a file that breaks the build for every later test, in an
order-dependent way that a fresh tree or a single test run never reproduces.
