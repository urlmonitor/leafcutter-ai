---
title: "CI: the typecheck and component-vocab jobs diff against a reachable merge base"
date: "2026-10-02"
time: "12:52"
type: manual
components: 
  - build_pipeline
summary: "The informational mypy job and the component-vocabulary gate no longer lose the pull request's merge base when main has moved on, so they check the files the pull request changed instead of failing or scanning the whole tree."
description: "Both jobs check out full history (fetch-depth: 0) and then ran git fetch --no-tags --depth=1 origin <base>. A depth-limited fetch into a full clone makes it shallow again at the base branch's tip, hiding that tip's parents. When main has advanced past the pull request's merge base, git diff origin/main...HEAD then has no common ancestor. The typecheck job failed with 'fatal: origin/main...HEAD: no merge base' and exit code 128 before mypy ran (PR #985, run 37006254096); it was red on the pull request and type-checked nothing. check_component_vocab.py --changed catches the same diff failure and falls back to a full-tree scan, so the blocking component-vocab gate silently stopped being diff-scoped and could fail a clean pull request for drift already on main. Both fetches now drop --depth, matching the changelog-presence job, which uses the same checkout and fetch without --depth. Reproduced locally in a --no-local clone that emulates actions/checkout with fetch-depth: 0 against a source whose main is three commits past the merge base: with --depth=1 the clone becomes shallow and the diff fails with exit code 128; without it the merge base resolves and the diff lists only the pull request's file. The test job's pinned-corpus git fetch --depth=1 origin <sha> is unchanged: it fetches one commit and does no merge-base diff."
---

## Entry

### Changed

- `.github/workflows/ci.yml` (`typecheck`) — the base-branch fetch before the three-dot
  diff no longer passes `--depth=1`, so the merge base stays reachable and mypy runs on the
  pull request's changed files even after main has moved on.
- `.github/workflows/ci.yml` (`component-vocab`) — the same fix for the fetch before
  `check_component_vocab.py --changed`, which had been silently falling back to a
  full-tree scan.
