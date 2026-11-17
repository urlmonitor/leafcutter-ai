---
title: "The local CI run type-checks as the required mypy ratchet does, and its red fails the run"
date: "2026-11-17"
time: "12:00"
type: manual
components:
  - build_pipeline
summary: "scripts/run_ci_local.py's typecheck gate now runs the same scripts/ci/mypy_ratchet.py call as CI's required 'mypy ratchet (new errors only)' check, read from ci.yml, against origin/main. It is blocking and on by default: a new mypy error, a new type-ignore or a could-not-check fails the local run."
description: >-
  BP-1300f-1-viii (new L3 under BP-1300f-1). The old gate ran informational
  `mypy ... scripts`, which aborts at once on "Duplicate module named
  window_total" and so checked nothing. The gate now reads the ratchet call out
  of .github/workflows/ci.yml job typecheck, so the pathspecs live only there,
  and runs it with origin/<--base-branch, default main> as the base. Ratchet
  exit 1 and exit 2 are FAIL; an unreadable ci.yml, or one with no single
  ratchet call, is FAIL (could not check) naming the file; a branch that
  changes no Python file in scope shows NOTHING INSPECTED, never PASS, and does
  not fail the run, as in CI. New --only and --base-branch options. The local
  run does not fetch: run `git fetch origin main` first for CI's exact merge
  base. ci.yml's comments no longer say the typecheck job is not a required
  check.
breaking: false
---

## Entry
