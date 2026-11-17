---
title: "The deploy-dependency rule in CLAUDE.md covers every file a guardrail reads, not only imported modules"
date: "2026-11-16"
time: "10:00"
type: manual
components: 
  - build_pipeline
summary: "The CLAUDE.md rule 'New Hook / Gate Dependencies Must Be in the Build Deploy-Manifest' now defines a dependency as any file the guardrail reads, describes the data-file failure, and points at the closure guard that enforces it."
description: "BP-900g-8-iii. The rule previously defined the dependency class by the ModuleNotFoundError a missing module raises, so a configuration JSON looked out of scope. It now names schemas, vocabularies, registries and data tables beside modules, describes the FileNotFoundError and silent-fallback symptoms of a missing data file, says to verify from an install that does not contain the package source tree and why the package workspace cannot show the gap, gives config/doc_types.json and config/ac_store_schema.json as non-code worked examples, and names compute_intra_package_closure and _check_intra_package_closure_guard as the enforcing mechanism. unit_tests/test_bp_900g_8_iii.py pins each claim and checks the named mechanism and example files exist. BP-900g-8-iii and its parent BP-900g-8 are marked done."
breaking: false
---

## Entry
