---
title: "A test declares whether it reads or mutates (TQ-600a-5)"
date: "2026-09-30"
time: "09:45"
type: manual
components: 
  - testing_quality
  - build_pipeline
summary: "Tests now declare themselves readers or mutators, and that declaration alone selects the shared reference layout or a private package copy."
description: "TQ-600a-5 lands the routing input the rest of TQ-600a is built on: a-2, a-8 and a-4 all consume it. pytest.ini registers shared_layout_reader and shared_layout_mutator; _select_route reads only the pytest marker, never a filename, path or glob; readers receive TQ-600a-1's single shared layout while mutators and undeclared tests receive a private copy that is never cached or reused. Undeclared is fail-safe rather than fail-fast: the test still runs, gets its own copy, and is named in the run's record so the omission is visible. declared_mutator_count and undeclared_count are reported as two separate named figures. Two defects were found while verifying, each more serious than the test that exposed it. First, _produce_private_copy ran a real build.py subprocess but never called emit_execution_signal, the sole emitter of deploy_executed, so every mutator and undeclared deploy was invisible to the log that a-6's deploy counter and a-2's bound are both built on; the suite could have regressed to dozens of real 59.8s deploys while the instrument still reported one. Second, replacing a grep-only marker-registration test with a behavioural one revealed that pytest.ini has never enforced marker strictness at all: on pytest 9.0.3 the --strict-markers token inside addopts has no effect (unregistered markers only warn, exit 0) while the strict_markers ini key correctly fails collection, so a misspelled declaration would have been silently ignored and quietly paid a private deploy. Both fixed. Four TQ-600a-1 tests gained an explicit reader marker, strictly additive with no assertion changed. Measured with AC_ENFORCE_STRICT=1: 7 passed for the a-1 files, 10 passed for the a-5 files, 5 passed for the reporting file after the strictness fix, ruff clean, AC store valid at 223 records. This does not by itself speed up the suite; the 77 build-spawning sites are migrated by TQ-600a-4."
---

## Entry
