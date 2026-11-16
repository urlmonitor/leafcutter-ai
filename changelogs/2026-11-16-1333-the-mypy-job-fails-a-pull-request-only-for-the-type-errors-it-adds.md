---
title: "The mypy job fails a pull request only for the type errors and type-ignores it adds"
date: "2026-11-16"
time: "13:33"
type: manual
components:
  - build_pipeline
summary: "CI's typecheck job is now 'mypy ratchet (new errors only)': it compares each changed file at the pull request's head with the same file at its merge base and fails only for new errors or new type-ignore comments. It is no longer continue-on-error, and it is not yet a required check."
description: >-
  BP-1300f-1 (new L1 BP-1300f under BP-1300, one L2, seven L3s). New
  scripts/ci/mypy_ratchet.py: lists the changed .py files with rename detection
  (git diff -M --diff-filter=ACMR, the job's twelve pathspecs unchanged), runs
  mypy on them at the head and in a temporary detached worktree of the merge base,
  matches errors by (head path, code, message) as multisets without line numbers,
  re-keys a renamed file's base errors from its old path, counts type-ignore
  comments with the tokenizer, and prints each new error with its head line and a
  remedy, plus one summary line. A run with nothing in scope says NOTHING INSPECTED;
  a mypy exit status other than 0 or 1, a status 1 with no error line (what
  `python -m mypy` gives when mypy is not installed), a failed `mypy --version`
  probe, a git failure or an unreadable file is COULD NOT CHECK (exit 2). The
  output names the mypy version it ran. .github/workflows/ci.yml job typecheck is renamed, loses
  continue-on-error and calls the module. Tests in unit_tests/build_guards/ build
  real git repositories and run the real module and mypy.
breaking: false
---

## Entry
