---
title: "Fix: commit guardian and exception hook unblocked; stale undeclared-dependency finding retracted (GE-120g-4, GE-108e)"
date: "2026-10-07"
time: "17:05"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: "Fixed a pre-commit check that was corrupting its own config file on every commit and a lint hook that blocked every Python edit on some machines, and withdrew an incorrect known-issue report about a missing dependency."
description: "check-negative-control-liveness rewrote commit_guardian.json unconditionally on every run via json.dumps with ensure_ascii defaulting True, re-escaping 110 em-dashes and failing the next commit's check-output-drift gate; it now snapshots the parsed document and writes only on real change, with ensure_ascii=False. The exception hook's ruff lookup used an OS executable search instead of python -m ruff, blocking Python writes on machines where ruff is only importable; it now tries the module path first. KI-BP-20261007 (undeclared aiosqlite dependency) is retracted as a stale-virtualenv false positive; aiosqlite arrives transitively via the declared langgraph-checkpoint-sqlite. test_exception_hook.py was split (new arms into test_ge_108e.py, shared helpers into _exception_hook_fixture.py) after crossing its 400-line limit. Covers GE-120g-4 and GE-108e; KI-CG-20260929 and KI-CG-20260914 moved to resolved."
commits: 
  - 5457880e
---

## Entry
