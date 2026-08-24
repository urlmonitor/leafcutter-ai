---
title: "Known Issues: Testing Quality"
description: "A test-isolation hazard in unit_tests/commit_guardian: sibling modules are cached in sys.modules under their bare name, so a stale deployed copy can shadow the canonical module for an entire pytest session and make a working fix look broken."
type: reference
status: active
created: 2026-08-19
last_updated: 2026-08-19
components:
  - testing_quality
related_docs:
  - docs/reference/fixture-policy.md
  - docs/architecture/adrs/ADR-001-self-hosting-boundary.md
---

# Known Issues: Testing Quality

## KI-TQ-1 — Bare-name `sys.modules` caching lets a stale deploy shadow the canonical module

**Severity: high.** It can hide a real fix *and* a real bug, and it has now bitten
twice in one epic.

`unit_tests/commit_guardian/test_commit_guardian_imports.py` uses a
`_import_module_from_dir` helper that caches modules in `sys.modules` under their
**bare name** (`_uniqueness_scanners`, not a package-qualified path).

Because `sys.modules` is process-global, the **first** load of that bare name in
a pytest session pins whichever copy existed at that moment for the rest of the
run. Every later test file doing `importlib.import_module("_uniqueness_scanners")`
silently gets the pinned copy.

This repository keeps a canonical source tree (`templates/scripts/commit_guardian/`)
and deployed copies (`scripts/commit_guardian/`, `.leafcutter/scripts/commit_guardian/`)
that `build.py` regenerates. If the deployed copy is stale when the suite starts,
the stale code is what the whole session tests.

**Observed twice:**

1. A stale deployed copy raised `TypeError: Finding.__init__() got an unexpected
   keyword argument 'declared_states'` against source that had the field.
2. A correct fix to `_fast_scan_top_level_id` appeared not to work — the full
   suite reproduced the *old* bug — because a pre-`build.py` deployed copy had
   been pinned first.

Both cost real diagnosis time, and the second nearly produced a wrong conclusion
about a fix that was in fact correct.

**Why it is worse than an ordinary flake:** the failure direction is not
consistent. A stale deploy can make a good fix look broken (wasted effort) or a
broken module look fixed (a false green that ships).

**Detection.** If a fix verifies green in isolation but fails in the full suite —
or vice versa — suspect this before suspecting the fix. Compare the canonical and
deployed copies directly:

```bash
diff templates/scripts/commit_guardian/<mod>.py scripts/commit_guardian/<mod>.py
```

**Workaround, and treat it as a standing rule.** Always run `build.py` before the
full `unit_tests/commit_guardian/` suite:

```bash
python3 scripts/build.py --target-dir <worktree_root> --force
```

**Suggested fix.** Import sibling modules under a package-qualified or
path-derived unique name so two copies cannot collide in `sys.modules`, or clear
the cached entry in a fixture teardown. Per this repo's own guidance, fix it in
the test files rather than a root `conftest.py` — a global conftest has too wide
a blast radius, and `importlib.reload()` is not a substitute because it masks
cold-import bugs.

## KI-TQ-2 — `test_ge_122e_3.py`'s tree-purity guard false-positives under concurrency

**Severity: medium.** It manufactures failures that are indistinguishable from
real ones.

`test_ge_122e_3.py` has a `tearDownModule` that proves the module never wrote to
the real repository — it snapshots `git status --porcelain` before the module
runs and compares afterwards. The guard itself is good practice: every fixture
operates on a `shutil.copytree`'d tempdir, and this catches a bug in the test
file's own fixture code escaping the tempdir.

The problem is that `git status --porcelain` is **repository-global**. The guard
cannot distinguish "this module escaped its tempdir" from "some other process
touched the tree", so **any** concurrent activity trips it:

```
RuntimeError: The real repository working tree changed during this test
module's run.
BEFORE: ... (12 modified files)
AFTER:  ... + tickets/.../03_TICKET-20260818-GE-122a-2.md
```

That diff is a *different* agent editing a *different* ticket. Nothing was wrong.

Observed three times in one session while several agents worked in one worktree.
Each occurrence cost an agent a diagnostic detour and a re-run. Two agents
correctly identified it as spurious; the danger is the third that does not — the
failure is loud, alarming, and points at the wrong thing, and the mirror-image
risk is an agent learning to dismiss this error and thereby missing a real
escape.

**Detection.** Compare the BEFORE and AFTER strings in the error. If the only
difference is a file this test module has no business touching, it is
interference.

**Workaround.** Do not run the suite while another agent is writing to the
worktree, and do not write to the worktree while a suite is running. One writer
at a time.

**Suggested fix.** Narrow the guard's scope: snapshot only the paths this module
could plausibly touch (`docs/acceptance-criteria/`, `docs/architecture/`,
`tickets/`) rather than the whole repository, or diff only against paths under
`_REPO_ROOT` that the module's own fixtures reference. Keep the guard — it is
the right idea, just too wide.

## KI-TQ-3 — A test-local oracle duplicated the production bug it should detect

**Severity: medium** as a pattern, even where the instance is fixed.

`test_ge_122e_3.py` defined its own local `_read_lifecycle_folder_names` helper
carrying the **identical basename-collapse defect** as the production
`_work_items_scanner.py` function (see KI-CG entries and GE-122a-2). The exit
gate's oracle shared the blind spot of the code it was written to verify.

It passed for exactly the reason the production bug was invisible: every real
lifecycle folder happens to sit one level under `tickets/`.

This is the same bias that once let a `files_touched` parser defect survive an
entire epic in this repository — synthetic fixtures and hand-written oracles
reproduce the implementation's assumptions, so they cannot falsify them.

**Detection.** When a test computes an expected value, ask whether it derives
that value **independently** or re-implements the logic under test. An oracle
that mirrors the implementation proves only self-consistency.

**Suggested fix (pattern, not instance).** Derive oracles from the data, not
from a reimplementation — read the config's full declared paths rather than
recomputing folder discovery. Where a helper must be shared between a test and
production code, import the production one so a bug shows up as a failure rather
than as agreement.
