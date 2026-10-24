---
title: "Changelog 7ce8a3e38 — contract-shrinking nets replaced skips and ignores new files"
date: "2026-10-24"
time: "13:44"
type: manual
components: 
  - commit_guardian
summary: "check-contract-shrinking no longer blocks a commit for replacing a test skip one-for-one or for a skip inside a brand-new test file; a skip added to an existing test still blocks."
description: "One commit (7ce8a3e38, fix). check_contract_shrinking.py now nets added skip/xfail lines against removed ones per file and per kind, reporting only the excess, and does not judge files the commit adds as new (decided from the staged diff against HEAD, so during a merge a branch-only test file is still judged). Test deletion detection is unchanged. GE-111f-1 is done; KI-CG-20261023-contract-shrinking-counts-moved-skips-as-added is resolved. test_ge_122e_1 no longer counts child ids such as GE-111f-1 as citations of GE-111f."
adrs: []
commits: 
  - 7ce8a3e38
breaking: false
---

## Entry
