---
title: "Fix approve_acs multi-line amended_by corruption and unproven success (KI-ACS-017)"
date: "2026-09-14"
time: "13:47"
type: manual
components: 
  - ac_store
summary: "Fixed an AC-store approval bug that could silently corrupt acceptance-criteria records while still reporting success."
description: "1 commit (ef2c63401), Bug Fixes. approve_acs.py's amended_by block delimiter matched only interior-line shapes, so a blank line inside a multi-line quoted or folded amended_by scalar ended the match early, truncating the rebuilt block and stranding the rest of the real block as invalid top-level text. Separately, _promote_leaf printed a success line and returned 0 without re-reading what it had written. Both fixed: block-end detection now finds the next column-0 top-level key (or end of document) instead of matching interior-line shapes, and the tool re-reads and re-parses its own output before reporting success, restoring the original bytes and exiting 1 on any write it cannot itself parse. On 2026-08-31 the two defects together destroyed 5 of 31 GE-123 AC records while reporting rc=0 for all 31."
commits: 
  - ef2c63401
breaking: false
---

## Entry
