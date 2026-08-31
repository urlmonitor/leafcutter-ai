---
title: A declared deploy source that goes missing now fails the build instead of logging a warning and shipping anyway
date: "2026-08-31"
time: "10:20"
type: manual
components: 
  - build_pipeline
summary: Fixed a build defect where a missing required file could ship silently with a warning; the build now stops and lists every missing declared file instead of reporting success anyway.
description: "3 commits (be12d44b2, 62c866aaf, c74f53004). build_phases.DeploySourceMissingError now carries a .failures list of {phase, entry, source_path}, and eight deploy sites -- build_ac_store, build_workflow_tools, build_knowledge_scripts, build_agent_support_scripts (two loops sharing one raise), _deploy_fast_lane_release_dependency, build_ac_store_docs, build_product_truth, build_build_orchestration_scripts -- accumulate every unresolvable declared entry and raise once at the end of their loop instead of warn-and-continue; main() catches it, prints each failure to stderr, and returns 1. Reaching all eight (the AC's n_location_rule is 'all') took five audit passes: three successive searches each missed a site their own search key could not match -- a loop using 'return 0' instead of 'continue', a bare print(\"[WARNING] ...\") instead of _log.warning, and a glob-shaped out-of-scope judgement that missed build_product_truth because its glob applies only within each declared subdirectory. Only reading every build_* and _deploy_* function and asking what each does when its named source is absent settled coverage. The fix immediately surfaced a stale test fixture: _build_synthetic_full_package() copied only templates/, scripts/ and config/ and had no docs/, so 19 tests that build against it began failing once a missing declared source became fatal; the fixture now derives its extra required directories from build_phases.py instead of hardcoding the path back in. Two known issues filed, not fixed: KI-BP-20260831-0728 (the hook-script integrity check strips the hooks/ path segment, so three real commit-guardian scripts are reported missing on every build) and KI-BP-20260831-1014 (seven declared sources -- build_vision, build_components_registry, build_ui_context, build_antigravity_instructions, build_feedback's config_src, build_commit_guardian's manifest, and two build_ticket_lifecycle manifest checks -- are still skipped with no log at all, plus a note that this ticket's own scope line used 'does it warn' as its boundary when the AC itself says the log is not the observable). Verified: full suite 4208 passed, 7 skipped, 6 xfailed, 0 failed; ruff clean; build.py --target-dir <scratch> exits 0 with deployed artefacts confirmed present in the output tree; red state independently demonstrated in a scratch mirror against the pre-fix blobs."
commits: 
  - be12d44b2
  - 62c866aaf
  - c74f53004
breaking: false
---

## Entry
