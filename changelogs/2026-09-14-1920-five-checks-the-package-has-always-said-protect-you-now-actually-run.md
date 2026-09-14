---
title: Five checks the package has always said protect you now actually run
date: "2026-09-14"
time: "19:20"
type: manual
components: 
  - commit_guardian
  - guardrail_engine
summary: "check-folder-density, check-test-fixture-bloat, check-sql-complexity, check-debug-scripts and check-ac-done-on-merge were documented in the package README with a severity column, several with populated settings blocks, one with autofix routing — and named by no hooks_manifest entry, so none had ever run. They are registered, and GE-120h is authored as the criterion that makes the gap between advertised and running a reportable condition rather than a silent one."
description: "A reader had four independent reasons to believe these gates were live (a README severity row, a config.py settings block, a commit_guardian.json settings entry, autofix routing) and no way to discover that only hooks_manifest.hooks causes a gate to run. This is the limit case of GE-120's promise: not a check that ran and misreported, but one never invited to run. All five are registered always_run with no files key, because four resolve their own staged set via git diff --cached and ignore argv, and a filter the script never consults is flagged as a contradiction by the reachability gate; for check-debug-scripts a location-anchored regex matching nothing would be classified unreachable outright. check-ac-done-on-merge is the exception and is described as it behaves: it consults neither argv nor the staged set, reading git diff HEAD~1 HEAD on the post-merge stage, and is the first post-merge entry in the manifest — the entry records that its git shim is installed only by setup_ticket_worktree.py, so a checkout that never ran that has no shim and the gate stays silent there, which would have reproduced the very defect being fixed. The four pre-commit gates were observed passing in their own registering commit. The new GE-120h tree required a child-limit waiver on GE-120, granted at a confirmation gate and recorded with its reasoning; its package-surface declaration was written against the live known issue where two approved records declared a config key that never existed, so every id and path in it was read off disk and it states explicitly that test_fixture_bloat is not a key, that absence being what keeps one gate inert and therefore safe to register. The ratchet baseline falls from fourteen to nine."
commits: 
  - 4c28df9c8
breaking: false
---

## Entry
