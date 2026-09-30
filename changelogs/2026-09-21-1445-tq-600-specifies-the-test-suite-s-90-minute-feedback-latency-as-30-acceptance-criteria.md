---
title: "TQ-600 specifies the test suite's 90-minute feedback latency as 30 acceptance criteria"
date: "2026-09-21"
time: "14:45"
type: manual
components: 
  - testing_quality
  - commit_guardian
summary: "No behavior changed here: the team wrote down, as 30 formally-approved acceptance criteria, why a full test run takes an hour and a half, and separately recorded a third way an existing safety-check hook can silently pass without having checked anything."
description: "2 commits, no source code changed. 577e0f45 authors TQ-600 under docs/acceptance-criteria/testing-quality/ (30 AC YAML files: goal TQ-600 plus three L1s TQ-600a/b/c, each carrying a justified child_limit_override, and 26 approved L2/L3 leaves), measuring a full pytest run at 1:29:47 with 63% of wall clock in 60 of 5318 tests that each spawn a real `build.py --target-dir` subprocess (59.8s per build, 77 call sites across 52 test files, zero session-scoped fixtures), and adds an Implementation Conventions entry to CLAUDE.md prohibiting new build.py spawns in tests pending the shared fixture the goal specifies. d81be182 records a third mechanism on known issue KI-CG-20260907: check_ac_limits.py resolves the AC store from cwd rather than from its staged-path argument, so a correct absolute path passed from the wrong working directory still exits 0 having checked nothing; it also carries a mechanical docs/INDEX.md regeneration (239 rows reordered, path separators normalised to forward slashes, no content change) triggered incidentally by the transform-doc-index pre-commit hook."
commits: 
  - 577e0f45
  - d81be182
breaking: false
---

## Entry

No behaviour changed in this release. A full pytest run currently measures 1:29:47, with
63% of that wall clock sitting in 60 of 5318 tests — every one of them spawning a real
`build.py --target-dir` subprocess (59.8s each, 77 call sites across 52 test files, zero
session-scoped fixtures to share the cost). TQ-600 authors that finding as a new goal in
the acceptance-criteria store — three L1s and 26 approved leaves — specifying what "fast
enough to actually run" means, and CLAUDE.md gains a convention forbidding new
`build.py --target-dir` spawns in tests ahead of implementation. Separately, a third
silent-pass mechanism was recorded against commit-guardian known issue KI-CG-20260907:
`check_ac_limits.py` resolves the AC store from the current working directory rather than
from its staged-path input, so a correct absolute path run from the wrong directory still
exits 0 having checked nothing.
