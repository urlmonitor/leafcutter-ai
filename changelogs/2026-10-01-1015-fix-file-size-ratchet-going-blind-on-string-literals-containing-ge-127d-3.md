---
title: "Fix file-size ratchet going blind on string literals containing /* (GE-127d-3)"
date: "2026-10-01"
time: "10:15"
type: manual
components: 
  - commit_guardian
  - precommit_hooks
summary: "Fixed a measurement bug in the file-size guardrail so it can no longer be tricked into undercounting a file's length by an innocent string of text."
description: "count_content_lines() in templates/scripts/commit_guardian/_file_size_ratchet.py used three bare, context-free regexes to strip C-style block comments and Python triple-quoted strings. A \"/*\" inside a string literal (or, as a second defect found by the blast-radius sweep, inside a '#'/'//' line comment) opened a phantom block comment that silently discarded every line up to the next unrelated \"*/\", so the gate could be defeated with no intent at all. The real-world case: an innocent \"changelogs/*.md\" in a template literal had been under-measuring templates/workflows-js/finalize-feature.js by 425 lines; a second instance was found in check_structural_change.py's own comment (\"collector/services/*/*.py\"). The three regexes are replaced by a single-pass state-tracking scanner that treats single-quoted, double-quoted, backtick, and line-comment spans as opaque (navigated over, not interpreted), while triple-quoted strings and block comments are still discarded exactly as before; the function signature and all call sites are unchanged. Blast radius across 1568 tracked files: 24 counts change (12 by more than 5 lines), zero files newly cross their limit. Verified via a stashed-fix red baseline (HEAD's real pre-fix module ran), six pre-existing ratchet suites green (33/33), and all 44 dependent files passing (145 passed, 8 subtests). One earlier local run showed 3 failures in this AC's own tests; confirmed to be a stale-deployment module-identity race, not a defect -- they pass together (23 passed) after rebuilding the deployment."
adrs: []
commits: 
  - 165c2b1e07dea2958eae798fb7a6f3e87fea1979
breaking: false
---

## Entry
