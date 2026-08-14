---
title: "Commit-guardian hooks are usable on merge commits and in worktrees"
date: "2026-08-14"
time: "02:30"
type: fix
components: 
  - commit_guardian
  - testing_quality
summary: "Fixes five commit-guardian gates that blocked correct work — three that failed any merge commit by judging the whole incoming branch, one that flagged its own test fixtures, and one that reported the git hook as missing in every worktree."
description: "All five were found by the gates firing on a routine merge of origin/main into a feature branch, where they blocked a commit that had introduced none of the problems reported. (1) check_ac_limits, check_ac_parent_covered_by and check_ac_schema read their staged set from a plain `git diff --cached`. A merge stages the ENTIRE incoming branch, so each gate judged every AC file the other side carried — demanding the merge author fix tree shapes, back-links and missing test_spec blocks in ACs they never touched. All three now detect MERGE_HEAD and intersect against `git diff --cached MERGE_HEAD`, leaving only files whose result differs from BOTH parents — the content the merge itself introduces. Non-merge commits are unaffected. (2) check_contract_shrinking matched its weakening patterns as `^\\+.*<token>`, so the token matched anywhere in an added line: docstrings, string literals, changelog prose, and synthetic diffs embedded in the guard's OWN test fixtures all counted as test weakening, and `@unittest.skip` matched as a prefix of the conditional `@unittest.skipUnless`. Patterns are now anchored to real call/decorator syntax at line start. (3) verify_precommit_active built `.git/config` as a path, but in a worktree `.git` is a FILE, so it raised NotADirectoryError and reported git_hook: false for every worktree even while the hook was installed and firing; it now resolves the shared git dir via the module's existing _resolve_git_commondir helper. Each fix is pinned by tests that assert BOTH directions — that genuine weakening/violations still fail, and that a normal non-merge commit still sees every staged file — including an end-to-end CLI run so a gate cannot be silently neutered into never firing. The three AC gates share one inherited test contract so they cannot drift apart. Known remaining debt, deliberately NOT hidden by these fixes: roughly 33 AC files on main fail the current schema (30 missing test_spec; BO-2000e-1, BO-2000e-1-i and BO-2000e-2 carry criteria as a list where an object is required). That is pre-existing content debt needing AC authorship, tracked separately."
breaking: false
---

## Entry
