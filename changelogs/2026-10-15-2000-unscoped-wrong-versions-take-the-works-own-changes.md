---
title: "A wrong version with no declared scope may change only the files the work itself changed"
date: "2026-10-15"
time: "20:00"
type: manual
components:
  - testing_quality
  - build_orchestration
summary: "When a named wrong version's test entries declare no in_scope_files, the writer's list and write steps and the wrong-version runner now give it the non-test files the work added or changed since --base-ref, marked scope: derived. Declared files still win. The runner itself refuses any alteration outside a name's scope, and a missing base ref stops the step with a named error instead of an empty or whole-repo scope."
description: "TQ-500g-1-x (fast lane; user decision 2026-10-15, approved at the review gate). New --base-ref on wrong_version_writer.py list and write (default HEAD). Owed items gain an additive scope key (declared|derived). Derived scope = A/M files from git diff --no-renames plus untracked non-ignored files, minus deleted files, test files, the AC store and refused paths; computed by one lazily-run shared diff helper in _wvr_scope (DiffCache) that the fix undone also uses, so each invocation runs git diff at most once and prepare_fix_undone is unchanged. The runner refuses a manifest entry outside its name's scope ('not prepared: <path> is not in scope for \"<name>\"'). Without this, 715 of 738 declared entries in the AC store would have had no scope and every work using them would stop before commit."
commits:
breaking: false
---

## Entry

Most existing requirements name the wrong versions their tests must catch but not the files
those wrong versions may touch. Instead of stopping every such work, the wrong-version step now
lets an unscoped wrong version change only the code the work itself changed, which is where the
fix lives. Files declared on a test entry still take precedence, and the runner refuses any
alteration outside those bounds.
