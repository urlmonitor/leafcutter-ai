---
title: "GE-127a-1 — check-file-size gate registered; run_hook.py stops leaving tracked .pyc behind"
date: "2026-09-07"
time: "12:41"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
  - ac_store
summary: "The file-length limit check now actually runs at commit time instead of sitting configured but silent, and a bug that could make it wrongly refuse an unrelated, well-behaved commit is fixed."
description: "Two coupled changes. (1) Registered check-file-size (GE-127a-1, GE-127a-1-i) in commit_guardian.json's hooks_manifest with always_run: true — the gate has existed, been configured, and been documented as Blocking for months while appearing on no entry: line, so this is the first time it runs on a real commit; it now refuses a commit that takes a covered file from under to over its permitted length, naming both the measured length and the limit, and stays silent on a compliant file even alongside an over-limit one in the same commit. (2) run_hook.py now passes PYTHONDONTWRITEBYTECODE=1 to the delegated hook process at all three dispatch sites, so a hook that imports a deployed module no longer leaves a .pyc beside it — in a project whose .gitignore does not exclude __pycache__ (true of every fresh consumer install, since build.py deploys no .gitignore), those .pyc files were tracked and pre-commit reported 'files were modified by this hook', failing the gate regardless of its own verdict. Change (2) is what makes (1) safe: registering the gate as always_run is what turned that latent condition into a live, commit-blocking regression. Also: check_file_size.py / _file_size_ratchet.py now raise CurrentLengthUnmeasurableError (exit 2 INDETERMINATE) instead of silently returning 0 when a staged file's current content cannot be opened or decoded (GE-127a-1-i), and five new unit test files were added under unit_tests/commit_guardian/ (test_ge_127a_1.py, plus test_ge_127a_1_i_named_situations.py, test_ge_127a_1_i_verdict_floor.py, test_ge_127a_1_i_entry_points.py and their shared _ge_127a_1_i_fixtures.py). The GE-127a-1-i coverage is split across three files because the newly registered gate refused the original single 467-line file on this very commit — its first real run, doing exactly what it was registered to do. Does not change which extensions are covered (.js/.ts/.sh limits are GE-127c-1, not built) and does not add the ratchet (GE-127b-1, already on main)."
breaking: false
---

## Entry
