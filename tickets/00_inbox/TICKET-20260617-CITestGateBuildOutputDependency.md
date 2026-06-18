---
title: "Enable a blocking CI test gate (resolve gitignored build-output dependency)"
status: todo
components:
  - testing_quality
  - build_pipeline
created: 2026-06-17
depends_on: []
priority: medium
roadmap_phase: phase_1
advances_current_outcome: false
requires_diagram: false
requires_adr: true
---

# Enable a blocking CI test gate (resolve gitignored build-output dependency)

## Actor / Goal

In order to enforce that the test suite stays green on every PR, we need the
pytest suite to run cleanly on a fresh checkout (as a CI runner sees it) so that
a blocking `test` job can be added to `.github/workflows/ci.yml` without flagging
spurious failures.

## Context

CI was introduced in `.github/workflows/ci.yml` with a **lint** job (blocking)
and a **typecheck** job (informational). A blocking **test** job was deliberately
omitted because the suite cannot run green on a fresh clone. This ticket tracks
the prerequisite work to close that gap.

**Root cause (diagnosed 2026-06-17):**

1. `scripts/commit_guardian/`, `scripts/doc_compliance/`, and `scripts/feedback/`
   are **gitignored build outputs** (see `.gitignore` lines 7–9), not tracked
   source. A CI runner does `git clone` and therefore does **not** have these
   directories.
2. ~36 tests import from those paths. For example,
   `tests/commit_guardian/test_commit_guardian_imports.py` reads
   `WORKTREE_ROOT / "scripts" / "commit_guardian"` and
   `tests/commit_guardian/test_diagram_type_enum.py` /
   `unit_tests/commit_guardian/test_transform_hooks_and_autofix_emission.py`
   invoke `scripts/commit_guardian/check_exception_handling.py` by path. On a
   clean checkout these fail at import / file-open.
3. Running the build does **not** fix this on a clean tree: `build.py`'s
   `build_commit_guardian` phase writes into the consolidated `.leafcutter/`
   output root (`.leafcutter/scripts/commit_guardian/`), and `install_shims`'
   `shim_map` only bridges `.claude/*` and `.gemini` — **not**
   `scripts/commit_guardian`. So after a current build, the path the tests read
   is still empty. A developer's working checkout only passes because it carries
   **stale pre-consolidation** outputs in `scripts/` (the dirs in
   `_PRE_CONSOLIDATION_PATHS` that `build.py --migrate` is designed to remove).

**Evidence:** In a developer checkout where `scripts/commit_guardian/` is
populated, the previously-failing tests pass (verified:
`test_commit_guardian_imports.py` + `test_diagram_type_enum.py` → 55 passed).
In a fresh `git worktree` at `origin/main`, the same suite fails ~36 tests at
import. So the tests themselves are correct; the failure is purely the missing
build outputs at the path the tests expect.

This is an architectural inconsistency between **where the build writes**
(consolidated `.leafcutter/scripts/...`) and **where the tests read**
(pre-consolidation `scripts/...`). It must be resolved at the repo level before
a CI test gate can be reliable.

## Acceptance Criteria

```gherkin
Given a fresh clone of the repository (no local build outputs present)
When the documented CI test command is run (install deps, build step if any, pytest)
Then the full suite under tests/ and unit_tests/ passes with zero failures
  and the result is deterministic across repeated runs

Given the resolution chosen for the build-output / test-path mismatch
When CI runs on a pull request
Then a blocking `test` job in .github/workflows/ci.yml runs the suite and fails
  the PR on any test failure

Given the test gate is green and enforced
When branch protection on main is reviewed
Then the required status checks include both `lint` and the new test check
```

## Design Decisions

Pick one approach (record the rationale in an ADR — `requires_adr: true`):

1. **Add a build step to CI + shim `scripts/commit_guardian` (etc.) into place.**
   Extend `install_shims`' `shim_map` (or the test bootstrap) so the consolidated
   `.leafcutter/scripts/...` outputs are bridged to the `scripts/...` paths the
   tests read, then run `python scripts/build.py --target-dir . --self-description-enforcement warning`
   before pytest in CI.
2. **Repoint the tests at the consolidated location** (`.leafcutter/scripts/...`)
   so no shim is needed, and run the build before pytest in CI.
3. **Stop gitignoring the build outputs** for the commit_guardian/doc_compliance/
   feedback dirs (track them), so a fresh clone has them. (Likely undesirable —
   conflicts with the consolidation/self-hosting design; weigh against ADR-001.)

Whichever is chosen, the suite must also be confirmed deterministic — earlier
runs showed counts swinging (2→11→15→17) that traced to the missing-build-output
state interacting with `pytest-randomly`; re-verify once outputs are present.

## Implementation Tasks

- [ ] Decide the resolution approach and record it in an ADR.
- [ ] Implement the chosen fix (shim_map extension / test repoint / gitignore change).
- [ ] Confirm `pytest tests unit_tests` is green and deterministic on a fresh
      `git worktree` of `origin/main` (build first if the approach requires it).
- [ ] Add a blocking `test` job to `.github/workflows/ci.yml` (install
      `requirements-dev.txt`, run the build step if needed, run pytest).
- [ ] Add the test check to branch-protection required status checks on `main`.

## Risk & Safety

- Touches money? No.
- Touches data? No — test/CI plumbing and build-output wiring only.
- Reversibility? Fully reversible (CI config + build/shim wiring).
- Shared contracts? The build output layout and `install_shims` `shim_map` are
  consumed by consumer-project installs — any shim change must be validated
  against a consumer install, not just the self-build, before merge.
