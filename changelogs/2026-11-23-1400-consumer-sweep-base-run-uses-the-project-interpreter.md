---
title: "The consumer-sweep check runs the base side with the project's interpreter"
date: "2026-11-23"
time: "14:00"
type: manual
components:
  - build_orchestration
summary: "consumer_sweep.py check (called by wrong_version_gate.py finish on every drive) runs each changed existing test at the base ref inside a git archive export. The export has no .git, so the interpreter was resolved from nothing and fell back to the bare running python; in an adopter whose dependencies live in a per-worktree .venv (DIAGraph) every base run crashed on the conftest import (pytest exit 4), every such file came back inconclusive, and the gate could never pass for a ticket that edits an existing test. Both sides now run with the interpreter resolved once from the live repo root (configured / .venv / uv / current, as before), the base side keeps the export as its working directory, and the export's src/ and root go first on PYTHONPATH so the .venv's editable install of the working tree's package cannot stand in for the base code."
description: "TQ-500g-3-ii. scripts/build_orchestration/_cs_runs.py resolves the judge from the live root and passes it to both sides, with the export's import roots for the base side; scripts/build_orchestration/_wvr_pytest.py run_selected accepts an optional judge and import_roots. New test unit_tests/build_orchestration/test_tq500g3ii_base_interpreter.py: an export without .git runs with the live root's .venv / uv interpreter on both sides (not sys.executable), and a real venv whose editable install points at the working tree still makes the base side import the base copy."
commits:
breaking: false
---

## Entry

The sweep check could never pass in projects that keep their dependencies in a per-worktree
virtual environment: the run of the tests at the base commit used the bare system Python and
failed to import the project. Both runs now use the project's own interpreter, and the base run
still imports the base commit's code.
