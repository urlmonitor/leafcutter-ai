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
