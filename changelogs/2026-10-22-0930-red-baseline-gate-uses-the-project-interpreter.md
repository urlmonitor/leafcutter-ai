---
title: "The red-baseline gate judges new tests with the project's own Python, and names an un-importable project package instead of reporting no red"
date: "2026-10-22"
time: "09:30"
type: manual
components:
  - build_orchestration
  - testing_quality
  - ac_store
summary: "The build routes launch the red-baseline gate as bare `python`, and the gate ran the new tests with that same interpreter. In an adopter whose dependencies live in a project venv (DIAGraph: a uv-managed .venv per worktree), conftest import failed, every new test read ERROR, and the gate reported no_red_outcome_among_new_tests, so the coder was never dispatched although the tests were genuinely red (17 red, 1 green by design). The gate now runs the tests with the project's interpreter, and an un-importable project package is a named refusal. TQ-500f-3-v."
description: "New scripts/ac_store/project_python.py resolves the interpreter: testing_context.python_command in skills_config.json, else the worktree's .venv, else `uv run --project <root> python` for a uv-managed project, else sys.executable. done_proof._run_pytest_and_parse, done_proof_kind_support's kind runner, the done-proof reachability observation and the wrong-version runner (_wvr_pytest) all run their child under it. verify_red_baseline and heavy_lane_gate report it as `interpreter`, the pytest-importable probe asks it rather than the launching process, and when every new test errors at collection because a top-level project package cannot be imported, the verdict is project_package_not_importable with a `refusal` naming the interpreter and the package. build-feature.js and build-ticket.js print that refusal in their halt. Deployed via AC_STORE_DEPLOY_MAP; `python_command` documented in skills_config.schema.json."
commits:
breaking: false
---

## Entry

In projects that keep their packages in a virtual environment, the check that runs before the
coder used the wrong Python, could not load the project, and stopped every build with a
misleading "no failing test" message. It now runs the tests with the project's own Python. If
that Python cannot load the project either, the check says exactly that, and names the Python.
