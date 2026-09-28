---
title: "KI-ACS-20260928 — the done-proof pytest rootdir walk has no upper bound, so a config file above the project can become the test run's cwd"
description: "KI-ACS-20260928 — the done-proof pytest rootdir walk has no upper bound, so a config file above the project can become the test run's cwd"
type: reference
category: reference
status: active
created: '2026-09-28'
last_updated: '2026-09-28'
components:
  - ac_store
related_docs:
  - docs/known-issues/ac-store.md
  - docs/known-issues/README.md
---

# KI-ACS-20260928 — the done-proof pytest rootdir walk has no upper bound, so a config file above the project can become the test run's cwd

> Index: [ac-store.md](../ac-store.md).

- **Severity:** low. Not reproduced; found in review.
- **Status:** open
- **Occurrences:** 0 observed (found in pr-reviewer review of PR #925, 2026-09-28)
- **Where:** `scripts/ac_store/_done_proof_phase_helpers.py`, `_resolve_pytest_run_cwd()`, the loop over `(common_ancestor, *common_ancestor.parents)`

**What the code does.** `_resolve_pytest_run_cwd()` picks the working directory for the pytest
subprocess that `done_proof._run_pytest_and_parse` starts. It walks up from the common ancestor
of the linked test files and returns the first directory that declares a pytest rootdir:
`pytest.ini`, `tox.ini` with `[pytest]`, `setup.cfg` with `[tool:pytest]`, or `pyproject.toml`
with `[tool.pytest.ini_options]` or `[tool.pytest]`. If nothing qualifies, it falls back to the
common ancestor. PR #925 added the walk to fix CI's "pytest run unfinished ... returncode 4":
pytest.ini's `-p scripts.ac_store.pytest_ac_enforcement` plugin could not be imported from the
test directory.

**The gap.** The walk stops only at the filesystem root. It is not bounded by the project root
or by the git top level. If a project has no qualifying config of its own, and a directory above
it does (a stray `pyproject.toml` with a pytest section in the user's home directory, or a
monorepo parent), that outer directory becomes the subprocess cwd. pytest then collects with
the other project's `addopts` and plugins. Linked tests can fail to import, or report "not run",
for reasons that have nothing to do with the criterion being checked.

**Why it is low.** It was not reproduced; nothing qualifying exists above this repo on the
developer machine or in CI. pytest's own rootdir discovery walks upward in the same unbounded
way, so the helper shows the same exposure pytest already has. A project with its own
`pytest.ini` or `pyproject.toml`, which leafcutter's install writes, stops the walk inside the
project.

**Fix direction.** Stop the walk at the project root that `verify_done_eligible` already knows
(or at `git rev-parse --show-toplevel`), and fall back to the common ancestor beyond it. Add a
test with a qualifying config above the fixture project, asserting the cwd stays inside the
project.
