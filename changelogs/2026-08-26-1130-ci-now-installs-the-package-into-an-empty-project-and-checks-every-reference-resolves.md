---
title: "CI now installs the package into an empty project and checks every reference resolves"
date: "2026-08-26"
time: "11:30"
type: manual
components: 
  - build_pipeline
  - commit_guardian
summary: "Adds the consumer-install-sim CI job (BP-900h-1): builds the package into a scratch directory that started empty, then fails, naming each one, if any script path referenced by a compiled agent template or skill does not resolve in the deployed tree."
description: "Implements BP-900h-1, the first ticket of EPIC-DeploymentCompleteness to be built. Three files. scripts/ci/check_consumer_install.py is a single invocable entry point (--package-dir, --target-dir, --skip-build; exit 0 clean, 1 unresolved references, 2 environment error) that creates a scratch project holding only a minimal skills_config.json, checks the package out beneath it, runs build.py --target-dir ., asserts the deployed root exists and contains scripts/ and agents/, and then resolves every script path referenced by a compiled template against the deployed tree. It reuses build_referential_integrity.extract_compiled_script_path_refs and build_propagation_audit.build_broken_ref_report unmodified rather than reimplementing the matching rules, so the job and the existing BP-900b/BP-900c machinery cannot drift apart. The ci.yml step passes arguments only and carries no logic of its own, so the tests and the workflow reach the same code — without that, every test would exercise a copy of the job and the step itself would stay unverified, which is the same one-surface-tested-other-surface-shipped shape the deployment-completeness work exists to close. The job is informational and is deliberately not added to any required-checks list; promotion is BP-900h-3's scope. Two tests in unit_tests/portability/test_consumer_simulation.py, both real-subprocess against a real tmp_path, no mocking. The red baseline was genuine and verified before any implementation existed (both failed with exit 2, file not found), and the negative case was proved twice: once by deleting a real deployed script and confirming the check names its exact path on stderr, and once by fault-injecting the detection path itself so the negative test was shown to fail on its real assertion rather than only on a missing-file precondition. That second proof mattered — the test's only previously observed failure was the precondition, so its actual detection logic had never been seen to fail. Also fixes two mypy errors in the new file: _import_audit_modules was annotated tuple[object, object], so every attribute access on the dynamically imported modules was an error; now tuple[ModuleType, ModuleType]. KNOWN GAP, REPORTED NOT FIXED: the minimal skills_config.json the script writes at the scratch-project root is inert. build.py's config auto-detection (scripts/config_loader.py:59-68) only looks under <target>/{.claude,.gemini,.cursor,.github,.cline}/skills_config.json, never a bare root file, and the script does not pass --config explicitly — so the simulated install runs on package defaults rather than that file. Every pass/fail condition the tests assert is honestly satisfied and the job is sound; but the AC's wording reads as though that file configures the build, and it does not. The sibling AC BP-900h-6, which adds a first-commit attempt to this same job, inherits the same premise. Full file:line evidence is in the ticket comments, left for a decision on whether it becomes an AC amendment or a known issue."
breaking: false
---

## Entry

### Why this job did not exist until now

`BP-900h-1` had sat `status: todo` since it was created on 2026-08-17 and had never been
modified. Its epic, `EPIC-DeploymentCompleteness`, has 1 of 14 tickets done and its PR #489
has been an untouched draft since 2026-08-18. It was built here as a focused PR rather than
by reviving that epic, which is the pattern the `BP-900` area has already been following —
#491, #499, #500, #511 and #537 all landed the same way.

It is also a prerequisite: `BP-900h-6` adds a first-commit step *inside* this job, and
`GE-122d-6` cannot register the commit-time uniqueness check without a job that can observe
the resulting fresh-install regression.

### Two process notes worth recording

**The worktree was created from a stale base.** It branched at `#547` — 27 commits behind
`origin/main` — despite an explicit instruction to branch from `origin/main`. This surfaced
as a single confusing test failure: `test_ge_122e_1` correctly reported that `GE-120c-6`, an
id present in the GE-120 goal folder on `origin/main`, was absent on disk. The tree was not
being renumbered; the branch simply predated the commit that added it. Resolved by merging
`origin/main` after committing, and confirmed by re-running that test alone.

**The `test-runner` phase could not sign itself off.** Dispatched twice; both times the
subagent ran the suite correctly but had no `Edit` tool available and so could not write its
own sign-off. Rather than spawn a third, the identical commands were run directly and the
substitution recorded honestly in the ticket rather than attributed to the agent.
