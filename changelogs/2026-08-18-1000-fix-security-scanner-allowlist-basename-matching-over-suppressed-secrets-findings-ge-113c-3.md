---
title: "fix(security-scanner): allowlist basename matching over-suppressed secrets findings (GE-113c-3)"
date: "2026-08-18"
time: "10:00"
type: manual
components: 
  - commit_guardian
  - build_pipeline
summary: Fixed a security scanner bug where allowlisting one file could silently hide real secrets findings in every other file with the same name anywhere in the repo.
description: "scan_secrets.py _is_suppressed matched allowlist entries by basename instead of path segments, so an allowlist entry for one file suppressed same-named files at any depth; replaced with a real segment-by-segment suffix match (a451db67f). Adds 8 behavioral tests for the suppression logic (4dceeba79), closes GE-113c-3 and its four child ACs in the store with implemented_by links, and decouples an unrelated BP-900g-4 test from the live AC store so it no longer breaks when those ACs are marked done (01494fb4c)."
pr: 463
commits: 
  - a451db67f
  - 537e1a6b2
  - 4dceeba79
  - 01494fb4c
---

## Entry
